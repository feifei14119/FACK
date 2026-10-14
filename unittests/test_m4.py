"""M4 tests: fixup passes, waitcnt recompute, verifier, analysis, evaluator helpers.

Run: python3.8 -m pytest tests/test_m4.py   (or the repo's run-tests helper)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parser, regions, emitter, waitcnt
from reorder.editor import RegionEditor
from reorder.passes import PassPipeline, LineDiff
from reorder.verifier import Verifier
from reorder.model import Kind, LineKind
from isa.gfx942.target import Gfx942Target

HERE = os.path.dirname(os.path.abspath(__file__))
SHADER = os.path.join(os.path.dirname(HERE), "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")
ATT_DIR = os.path.join(os.path.dirname(HERE), "client", "poc_kl", "fp8_blockscale_gemm", "att")


def _load(src):
    prog = parser.parse(src)
    return prog, Gfx942Target.from_program(prog)


def _wait_lines(prog):
    return [ln for ln in prog.lines
            if ln.kind is LineKind.INSTR and (ln.opcode or "").startswith("s_waitcnt")]


# --- waitcnt recompute --------------------------------------------------
def test_recompute_full_drain():
    src = (".text\nk:\n"
           "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen\n"
           "  buffer_load_dwordx4 v[4:7], v9, s[0:3], 0 offen\n"
           "  v_add_f32 v20, v0, v4\n"
           "  s_endpgm\n")
    prog, t = _load(src)
    waitcnt.recompute(prog, t)
    waits = _wait_lines(prog)
    assert len(waits) == 1, waits
    assert waits[0].raw.strip() == "s_waitcnt vmcnt(0)", waits[0].raw


def test_recompute_partial_count():
    # consumer uses only the FIRST of two loads -> vmcnt(1)
    src = (".text\nk:\n"
           "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen\n"
           "  buffer_load_dwordx4 v[4:7], v9, s[0:3], 0 offen\n"
           "  v_add_f32 v20, v0, v0\n"
           "  s_endpgm\n")
    prog, t = _load(src)
    waitcnt.recompute(prog, t)
    waits = _wait_lines(prog)
    assert len(waits) == 1
    assert "vmcnt(1)" in waits[0].raw, waits[0].raw


def test_recompute_idempotent():
    src = (".text\nk:\n"
           "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen\n"
           "  v_add_f32 v20, v0, v0\n"
           "  s_endpgm\n")
    prog, t = _load(src)
    waitcnt.recompute(prog, t)
    first = emitter.emit(prog)
    prog2, t2 = _load(first)
    waitcnt.recompute(prog2, t2)
    assert emitter.emit(prog2) == first


def test_loop_carried_double_buffer():
    # Software-pipelined loop: consume buffer loaded LAST iteration, then refill.
    # 2 loads/iter, double-buffered: at the first consumer the producer is the
    # previous iteration's load of the SAME buffer -> exactly 1 other (the other
    # buffer's) load may still be in flight -> steady-state vmcnt(1).
    body = [
        "  v_add_f32 v20, v0, v0",                              # consume buf A (prev iter)
        "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen",    # refill A for next iter
        "  v_add_f32 v21, v4, v4",                              # consume buf B (prev iter)
        "  buffer_load_dwordx4 v[4:7], v9, s[0:3], 0 offen",    # refill B for next iter
    ]
    prog, t = _load(".text\nk:\nloop:\n" + "\n".join(body) +
                    "\n  s_cbranch_scc0 loop\n  s_endpgm\n")
    instrs = [ln for ln in prog.lines if ln.kind is LineKind.INSTR
              and (ln.opcode or "").lower() in ("v_add_f32", "buffer_load_dwordx4")]
    need = waitcnt.compute_waits_loop(instrs, t)
    # the two v_add consumers should each get vmcnt(1) in steady state
    vm_waits = sorted(spec.get("vm") for spec in need.values() if "vm" in spec)
    assert vm_waits == [1, 1], (vm_waits, need)


def test_linear_vs_loop_aware_differ():
    # Prefetch loop: consumer reads BEFORE the (textually later) producer; the
    # linear pass sees no prior producer (wrong -> no wait), loop-aware binds to
    # the previous iteration (correct -> a wait appears).
    body = ["  v_add_f32 v20, v0, v0",
            "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen"]
    prog, t = _load(".text\nk:\nloop:\n" + "\n".join(body) +
                    "\n  s_cbranch_scc0 loop\n  s_endpgm\n")
    instrs = [ln for ln in prog.lines if ln.kind is LineKind.INSTR
              and (ln.opcode or "").lower() in ("v_add_f32", "buffer_load_dwordx4")]
    linear = waitcnt.compute_waits(instrs, t)
    looped = waitcnt.compute_waits_loop(instrs, t)
    assert all("vm" not in s for s in linear.values())     # linear misses it
    assert any("vm" in s for s in looped.values())          # loop-aware catches it


# --- fixup pipeline + reversibility -------------------------------------
def test_pipeline_revert_restores():
    prog, t = _load(open(SHADER).read())
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    before = list(prog.lines)
    pipe = PassPipeline(t.fixup_pipeline(region=loop, recompute_waitcnt=True))
    diffs = pipe.run(prog, t)
    assert any(d.changed for d in diffs)
    PassPipeline.revert(prog, diffs)
    assert prog.lines == before


# --- forced nop ----------------------------------------------------------
def test_forced_nop_inserts_for_close_reader():
    src = (".text\nk:\n"
           "  v_mfma_f32_16x16x16_bf16 v[44:47], a[0:1], a[2:3], v[44:47]\n"
           "  v_add_f32 v50, v44, v60\n"
           "  s_endpgm\n")
    prog, t = _load(src)
    from isa.gfx942.passes import ForcedNopPass
    ForcedNopPass().run(prog, t)
    nops = [ln for ln in prog.lines if (ln.opcode or "") == "s_nop"]
    # 16x16x16 MFMA result read latency == 3 slots (classify.MFMA_READ_LATENCY);
    # consumer is adjacent (0 slots in between) -> pad 3 s_nop.
    assert len(nops) == 3, [ln.raw for ln in prog.lines]


def test_forced_nop_skips_mfma_chain():
    src = (".text\nk:\n"
           "  v_mfma_f32_16x16x16_bf16 v[44:47], a[0:1], a[2:3], v[44:47]\n"
           "  v_mfma_f32_16x16x16_bf16 v[44:47], a[4:5], a[6:7], v[44:47]\n"
           "  s_endpgm\n")
    prog, t = _load(src)
    from isa.gfx942.passes import ForcedNopPass
    ForcedNopPass().run(prog, t)
    nops = [ln for ln in prog.lines if (ln.opcode or "") == "s_nop"]
    assert len(nops) == 0


# --- verifier ------------------------------------------------------------
def test_verifier_detects_missing_wait():
    src = (".text\nk:\n"
           "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen\n"
           "  v_add_f32 v20, v0, v0\n"
           "  s_endpgm\n")
    prog, t = _load(src)  # no wait at all -> insufficient
    res = Verifier(t).verify(prog)
    assert not res.ok
    assert any("not synced" in v for v in res.violations)
    # after recompute it becomes sufficient
    waitcnt.recompute(prog, t)
    assert Verifier(t).verify(prog).ok


def test_verifier_loop_carried_detects_missing_wait():
    # Loop with a real cross-iteration dep but NO waitcnt -> loop-aware verify
    # must flag it (a non-loop-aware check would miss it).
    body = ["  v_add_f32 v20, v0, v0",
            "  buffer_load_dwordx4 v[0:3], v8, s[0:3], 0 offen"]
    src = ".text\nk:\nloop:\n" + "\n".join(body) + "\n  s_cbranch_scc0 loop\n  s_endpgm\n"
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    res = Verifier(t, analysis=a).verify(prog)
    assert not res.ok
    assert any("not synced" in v for v in res.violations)


def test_verifier_barrier_count_locked():
    src = (".text\nk:\n  s_barrier\n  s_endpgm\n")
    prog, t = _load(src)
    ref, _ = _load(src)
    # remove the barrier -> invariant must fire
    prog.lines = [ln for ln in prog.lines if (ln.opcode or "") != "s_barrier"]
    res = Verifier(t, reference=ref).verify(prog)
    assert any("barrier count" in v for v in res.violations)


# --- real kernel end-to-end ---------------------------------------------
def test_real_kernel_original_waits_reg_sufficient():
    # The hand-written kernel's existing waits must satisfy the loop-aware
    # (cross-iteration) reg-carried sufficiency check as-is.
    prog, t = _load(open(SHADER).read())
    a = regions.analyze(prog, t)
    res = Verifier(t, analysis=a).verify(prog)
    assert res.ok, res.violations[:5]


def test_real_kernel_coldstart_reorder_fixup_verify():
    src = open(SHADER).read()
    prog, t = _load(src)
    ref, _ = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
    ed.distribute_evenly(Kind.DS_READ, 0, len(ed.anchors(Kind.MFMA)) - 1)
    ed.materialize()
    # cold-start: recompute the loop's waits (loop-aware) + forced nop
    PassPipeline(t.fixup_pipeline(region=loop, recompute_waitcnt=True)).run(prog, t)
    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    assert res.ok, res.violations[:3]
    out = emitter.emit(prog)
    reparsed = parser.parse(out)
    nb_out = sum(1 for ln in reparsed.lines if (ln.opcode or "").startswith("s_barrier"))
    nb_ref = sum(1 for ln in ref.lines if (ln.opcode or "").startswith("s_barrier"))
    assert nb_out == nb_ref


# --- analysis: pure helpers ---------------------------------------------
def test_parse_codeobj_filename():
    from analysis import perf
    assert perf.parse_codeobj_filename(
        "memory1076064#offset=0x277c800&size=32648.out") == (0x277c800, 32648)
    assert perf.parse_codeobj_filename("foo.att") is None


def test_discover_real_dump_dir():
    if not os.path.isdir(ATT_DIR):
        return  # dump dir not present in this checkout
    from analysis import perf
    found = perf.discover_dump(ATT_DIR)
    assert found["att_files"], "expected .att files"
    assert found["code_objects"], "expected code-object .out files"
    for (_id, base, size, path) in found["code_objects"]:
        assert size > 0 and path.endswith(".out")


def test_kernel_symbols_detection_is_generic():
    # the engine derives WHICH kernel to trace from the .s, not a hardcoded name.
    from reorder import parser
    from isa.gfx942.target import Gfx942Target
    src = (".text\n"
           ".amdhsa_kernel my_custom_kernel\n"
           ".end_amdhsa_kernel\n"
           ".amdhsa_kernel second_kernel\n"
           ".end_amdhsa_kernel\n")
    prog = parser.parse(src)
    t = Gfx942Target()
    assert t.kernel_symbols(prog) == ["my_custom_kernel", "second_kernel"]
    # .end_amdhsa_kernel must NOT be mistaken for a kernel symbol
    assert "end_amdhsa_kernel" not in "".join(t.kernel_symbols(prog))


def test_evaluator_att_config_injects_detected_kernel():
    # the GPU evaluator writes a per-run ATT config with KERNEL=<under test>,
    # never relying on a hardcoded input.txt kernel filter.
    import tempfile
    from harness.evaluator import GpuTestcaseEvaluator
    from isa.gfx942.target import Gfx942Target
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "input.txt"), "w") as f:
            f.write("att: TARGET_CU=F\nSE_MASK=0x0F\n#KERNEL=stale\nDISPATCH=1\n")
        # explicit name
        ev = GpuTestcaseEvaluator(d, target=Gfx942Target(), kernel_name="foo_kernel")
        cfg = ev._write_att_config(ev.detect_kernel_name("/nonexistent.s"))
        body = open(os.path.join(d, cfg)).read()
        assert "KERNEL=foo_kernel" in body
        assert "DISPATCH=1" not in body and "#KERNEL=stale" not in body
        assert "TARGET_CU=F" in body                 # params preserved
        # auto-detect from a candidate .s
        s = os.path.join(d, "cand.s")
        with open(s, "w") as f:
            f.write(".text\n.amdhsa_kernel auto_k\n.end_amdhsa_kernel\n")
        ev2 = GpuTestcaseEvaluator(d, target=Gfx942Target())
        assert ev2.detect_kernel_name(s) == "auto_k"


def test_resolve_decoder_dir():
    import tempfile
    from analysis import perf
    saved = os.environ.pop("TESTFT_ATT_DECODER_DIR", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "decoder")
            os.makedirs(d)
            with open(os.path.join(d, perf._DECODER_SO), "wb") as f:
                f.write(b"\x7fELF")
            # explicit arg with the backend .so wins
            assert perf.resolve_decoder_dir(d) == d
            # $TESTFT_ATT_DECODER_DIR resolves it too
            os.environ["TESTFT_ATT_DECODER_DIR"] = d
            assert perf.resolve_decoder_dir() == d
            # a dir WITHOUT the .so is ignored -> falls through to candidates
            empty = os.path.join(tmp, "empty")
            os.makedirs(empty)
            os.environ["TESTFT_ATT_DECODER_DIR"] = empty
            got = perf.resolve_decoder_dir()
            assert got != empty
    finally:
        os.environ.pop("TESTFT_ATT_DECODER_DIR", None)
        if saved is not None:
            os.environ["TESTFT_ATT_DECODER_DIR"] = saved


def test_resolve_decoder_dir_pip_devel_sibling():
    import tempfile
    from unittest import mock
    from analysis import perf
    with tempfile.TemporaryDirectory() as tmp:
        core = os.path.join(tmp, "_rocm_sdk_core")
        os.makedirs(os.path.join(core, "lib"))
        with open(os.path.join(core, "lib", perf._DECODER_SO + ".0.2"), "wb") as f:
            f.write(b"\x7fELF")
        devel = os.path.join(tmp, "_rocm_sdk_devel", "lib")
        os.makedirs(devel)
        with open(os.path.join(devel, perf._DECODER_SO), "wb") as f:
            f.write(b"\x7fELF")
        env = {k: v for k, v in os.environ.items()
               if k not in ("TESTFT_ATT_DECODER_DIR", "AMDGPU_ATT_DECODER_DIR")}
        env["ROCM_PATH"] = core
        with mock.patch.dict(os.environ, env, clear=True):
            assert perf.resolve_decoder_dir() == devel
        assert perf._pip_devel_lib(os.path.join(tmp, "rocm")) is None


def test_aggregate_and_bottleneck():
    from analysis import perf, bottleneck
    from isa.gfx942.perf_schema import GFX942_ATT_SCHEMA
    insts = [
        perf.DecodedInst(0, 0, 0, 0, 1, 100, 5, 0, 0),   # LDS stall heavy
        perf.DecodedInst(0, 0, 0, 1, 1, 90, 5, 0, 0),    # LDS
        perf.DecodedInst(0, 0, 0, 2, 1, 5, 6, 0, 0),     # VALU small stall
    ]
    stats = perf.aggregate(insts, GFX942_ATT_SCHEMA)
    assert stats["n_inst"] == 3
    assert stats["by_dimension_stall"]["lds"] == 190
    d = bottleneck.classify(stats, GFX942_ATT_SCHEMA)
    assert d["bottleneck"] == "lds"
    assert any("ds_read" in h for h in d["hints"])


# --- evaluator: pure stdout parsing -------------------------------------
def test_evaluator_stdout_parsers():
    from harness.evaluator import parse_correctness_stdout, parse_perf_stdout
    assert parse_correctness_stdout("...\n#TEST PASSED\n") is True
    assert parse_correctness_stdout("#TEST FAILED") is False
    assert parse_correctness_stdout("nothing") is None
    t, g = parse_perf_stdout("m:128,n:128,k:128,time: 0.123456,gflops:1234.567")
    assert abs(t - 0.123456) < 1e-9 and abs(g - 1234.567) < 1e-3


def _wrap(fn):
    def method(self):
        fn()
    return method


_attrs = {name: _wrap(obj) for name, obj in dict(globals()).items()
          if name.startswith("test_") and callable(obj)}
M4Tests = type("M4Tests", (unittest.TestCase,), _attrs)


if __name__ == "__main__":
    unittest.main()
