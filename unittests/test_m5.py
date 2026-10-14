"""M5 tests: LDS-slot-precise waitcnt recompute + barrier LDS-release fence.

Covers the two memory-ordering constraints invisible to register tracking that
made M4's from-scratch recompute unsafe:
  * LDS round-trip (buffer_load...lds -> ds_read), resolved per-buffer-band
  * barrier LDS-release fence (lgkmcnt(0) before every s_barrier)

Run: python3.8 -m pytest tests/test_m5.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parser, regions, emitter, waitcnt, optlevel
from reorder.verifier import Verifier
from reorder.model import Kind, LineKind
from isa.gfx942.target import Gfx942Target
from isa.gfx942.lds import build_lds_model

HERE = os.path.dirname(os.path.abspath(__file__))
SHADER = os.path.join(os.path.dirname(HERE), "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


def _load(src):
    prog = parser.parse(src)
    return prog, Gfx942Target.from_program(prog)


def _instrs(prog):
    return [ln for ln in prog.lines if ln.kind is LineKind.INSTR and ln.opcode]


# A minimal double-buffered LDS loop: base chain s2=root+0, s3=root+256
# (stride 256); two lds-loads fill buf0/buf1; two ds_reads read offset 0 / 256.
_DBUF = """.text
k:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 0x100, s2
loop:
  s_waitcnt vmcnt(0) & lgkmcnt(0)
  s_barrier
  ds_read_b64 v[10:11], v20 offset:0
  ds_read_b64 v[12:13], v20 offset:256
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_cbranch_scc0 loop
  s_endpgm
"""


# --- LDS buffer model resolution ----------------------------------------
def test_lds_model_resolves_two_buffers():
    prog, t = _load(_DBUF)
    m = build_lds_model(_instrs(prog), t)
    assert m.resolved
    assert m.stride == 256
    assert m.n_buffers == 2
    # read offsets 0 / 256 map to buffer band 0 / 1
    reads = sorted(m.read_idx.values())
    assert reads == [0, 1], reads
    writes = sorted(m.write_idx.values())
    assert writes == [0, 1], writes


def test_lds_model_read_write_bands_match():
    prog, t = _load(_DBUF)
    instrs = _instrs(prog)
    m = build_lds_model(instrs, t)
    # the ds_read at offset 256 must share a band with the lds-load whose m0
    # base is s3 (== root+256), NOT the s2 (root+0) load.
    by_op = {}
    for ln in instrs:
        op = (ln.opcode or "").lower()
        if t.classify(op, ln.operands) is Kind.DS_READ:
            off = next((tok.split(":")[1] for f in ln.operands for tok in f.split()
                        if tok.startswith("offset:")), "0")
            by_op[("read", off)] = m.read_buffer(ln.idx)
    assert by_op[("read", "0")] == 0
    assert by_op[("read", "256")] == 1


def test_lds_model_stride_excludes_intra_buffer_imm():
    # base chain stride 0x400; each buffer has intra-buffer slot imms 0/0x100.
    src = """.text
k:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 0x400, s2
loop:
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0x100, s2
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v2, s[4:7], 0 offen lds
  ds_read_b64 v[10:11], v20 offset:0
  ds_read_b64 v[12:13], v20 offset:1024
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    m = build_lds_model(_instrs(prog), t)
    assert m.resolved
    assert m.stride == 1024, m.stride          # 0x400, NOT gcd'd with 0x100 slots
    assert m.n_buffers == 2


def test_lds_model_unresolved_falls_back():
    # m0 base from an unfoldable (two-register) add -> model not resolved.
    src = """.text
k:
loop:
  s_add_u32 m0, s9, s8
  buffer_load_dword v0, s[4:7], 0 offen lds
  ds_read_b64 v[10:11], v20 offset:0
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    m = build_lds_model(_instrs(prog), t)
    assert not m.resolved
    # recompute must still run (conservative single-bucket) and be verifiable
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    a2 = regions.analyze(prog, t)
    assert Verifier(t, analysis=a2).verify(prog).ok


# --- buffer-precise ds_read vmcnt ---------------------------------------
# Barrier-free double-buffer loop: the ONLY thing that can protect a ds_read is
# the per-read LDS round-trip model (no draining barrier to subsume it). Each
# read consumes its band's PREVIOUS-iteration fill, then both bands are refilled.
_DBUF_NOBAR = """.text
k:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 0x100, s2
loop:
  ds_read_b64 v[10:11], v20 offset:0
  ds_read_b64 v[12:13], v20 offset:256
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_cbranch_scc0 loop
  s_endpgm
"""


def test_ds_read_binds_to_same_buffer_load():
    prog, t = _load(_DBUF_NOBAR)
    instrs = _instrs(prog)
    m = build_lds_model(instrs, t)
    assert m.resolved and m.n_buffers == 2
    need = waitcnt.compute_waits_loop(instrs, t, lds_model=m)
    ds = [ln for ln in instrs
          if t.classify((ln.opcode or "").lower(), ln.operands) is Kind.DS_READ]
    # both reads bind (cross-iteration) to their own band's lds-load -> vm wait
    specs = [need.get(ln.idx, {}) for ln in ds]
    assert all("vm" in s for s in specs), specs


def test_ds_read_buffer_precision_distinguishes_bands():
    # buf0's read must NOT be forced to wait for buf1's (unrelated) lds-load:
    # with the precise model the buf0 read binds only to the buf0 load. Compare
    # against the conservative single-bucket (no model) which over-binds.
    prog, t = _load(_DBUF_NOBAR)
    instrs = _instrs(prog)
    m = build_lds_model(instrs, t)
    precise = waitcnt.compute_waits_loop(instrs, t, lds_model=m)
    coarse = waitcnt.compute_waits_loop(instrs, t, lds_model=None)
    first_read = next(ln for ln in instrs
                      if t.classify((ln.opcode or "").lower(), ln.operands) is Kind.DS_READ)
    # the precise binding for the first read is looser-or-equal (binds to its own
    # band's load) than the conservative one (binds to the newest of ANY band).
    assert precise[first_read.idx]["vm"] >= coarse[first_read.idx]["vm"]


# --- barrier LDS-release fence ------------------------------------------
def test_recompute_inserts_lgkmcnt0_before_barrier():
    prog, t = _load(_DBUF)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    # every barrier must be immediately preceded by a wait that drains lgkm to 0
    lines = [ln for ln in prog.lines if ln.kind is LineKind.INSTR and ln.opcode]
    for i, ln in enumerate(lines):
        if (ln.opcode or "").lower() == "s_barrier":
            prev = lines[i - 1]
            assert (prev.opcode or "").startswith("s_waitcnt"), prev.raw
            assert "lgkmcnt(0)" in prev.raw, prev.raw


def test_barrier_fence_drains_only_read_band():
    # Triple-buffer-style body: barrier, then ds_reads of ONE band, then loads
    # to ALL bands. The barrier vm-fence must drain only the READ band's loads,
    # leaving the other bands' (prefetch) loads in flight -> looser vmcnt than a
    # drain-all fence.
    src = """.text
k:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 0x100, s2
  s_add_u32 s4, 0x100, s3
loop:
  s_waitcnt lgkmcnt(0)
  s_barrier
  ds_read_b64 v[10:11], v20 offset:0
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s4
  buffer_load_dword v2, s[4:7], 0 offen lds
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    instrs = _instrs(prog)
    m = build_lds_model(instrs, t)
    assert m.resolved and m.n_buffers == 3
    # the barrier reads only band 0 (offset 0)
    bands = waitcnt._barrier_read_bands(instrs, t, m)
    bar = next(ln for ln in instrs if (ln.opcode or "").lower() == "s_barrier")
    assert bands.get(bar.idx) == {0}, bands

    # band-scoped fence must be looser-or-equal than drain-all (keeps band1/2
    # prefetch in flight): compare the barrier's recomputed vmcnt both ways.
    scoped = waitcnt.compute_waits_loop(instrs, t, lds_model=m)
    # force drain-all by clearing the look-ahead map on a fresh board
    cm = t.counter_model()
    board = waitcnt._Scoreboard(cm.names, lds_model=m)  # no barrier_bands set
    alldrain = {}
    for _ in range(8):
        cur = {}
        for ln in instrs:
            s = board.step(ln, t)
            if s:
                cur[ln.idx] = s
        alldrain = cur
    bvm_scoped = scoped.get(bar.idx, {}).get("vm")
    bvm_all = alldrain.get(bar.idx, {}).get("vm")
    assert bvm_scoped is not None and bvm_all is not None
    assert bvm_scoped >= bvm_all, (bvm_scoped, bvm_all)


def test_verifier_flags_missing_barrier_fence():
    # barrier preceded by a too-loose lgkm wait -> fence violation.
    src = """.text
k:
loop:
  ds_read_b64 v[10:11], v20 offset:0
  ds_read_b64 v[12:13], v20 offset:64
  ds_read_b64 v[14:15], v20 offset:128
  ds_read_b64 v[16:17], v20 offset:192
  s_waitcnt lgkmcnt(2)
  s_barrier
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    res = Verifier(t, analysis=a).verify(prog)
    assert any("barrier LDS-release" in v for v in res.violations), res.violations


def test_verifier_flags_missing_ds_read_roundtrip():
    # lds-load fills a buffer, ds_read reads it next iter with NO vmcnt -> flagged.
    src = """.text
k:
  s_add_u32 s2, 0, s0
loop:
  ds_read_b64 v[10:11], v20 offset:0
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    res = Verifier(t, analysis=a).verify(prog)
    assert any("LDS round-trip" in v for v in res.violations), res.violations


# --- real kernel: recompute_only is verifiable + structurally sound ------
def test_real_kernel_recompute_only_verifies():
    src = open(SHADER).read()
    prog, t = _load(src)
    ref, _ = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    assert res.ok, res.violations[:5]


def test_real_kernel_recompute_buffers_resolved():
    src = open(SHADER).read()
    prog, t = _load(src)
    m = t.lds_roundtrip_model(_instrs(prog))
    assert m.resolved
    assert m.n_buffers == 3                      # triple-buffered
    assert m.stride == 4224


def test_real_kernel_every_barrier_has_lgkmcnt0():
    src = open(SHADER).read()
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    lines = [ln for ln in prog.lines if ln.kind is LineKind.INSTR and ln.opcode]
    nbar = 0
    for i, ln in enumerate(lines):
        if (ln.opcode or "").lower() == "s_barrier" and i > 0:
            prev = lines[i - 1]
            if (prev.opcode or "").startswith("s_waitcnt"):
                # loop-region barriers get the recomputed fence
                if "lgkmcnt(0)" in prev.raw:
                    nbar += 1
    assert nbar >= 6, nbar                        # 6 unrolled sub-iteration barriers


def test_real_kernel_recompute_preserves_barrier_count():
    src = open(SHADER).read()
    prog, t = _load(src)
    ref, _ = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    out = parser.parse(emitter.emit(prog))
    nb_out = sum(1 for ln in out.lines if (ln.opcode or "").startswith("s_barrier"))
    nb_ref = sum(1 for ln in ref.lines if (ln.opcode or "").startswith("s_barrier"))
    assert nb_out == nb_ref


# --- optimization-level switch (reorder.optlevel) -----------------------
def test_optlevel_policy_decode():
    # L0 drain-all; L1 band look-ahead; L2 adds per-instruction reorder.
    assert (optlevel.policy(0).barrier_band_scoped, optlevel.policy(0).reorder) == (False, False)
    assert (optlevel.policy(1).barrier_band_scoped, optlevel.policy(1).reorder) == (True, False)
    assert (optlevel.policy(2).barrier_band_scoped, optlevel.policy(2).reorder) == (True, True)
    # monotonic: each knob, once on, stays on
    for knob in ("barrier_band_scoped", "reorder"):
        seq = [getattr(optlevel.policy(n), knob) for n in range(3)]
        assert seq == sorted(seq), (knob, seq)
    # L3 SEARCH caps == L2 (its product is an L2-class schedule)
    assert (optlevel.policy(3).barrier_band_scoped, optlevel.policy(3).reorder,
            optlevel.policy(3).reorder_alu) == (True, True, False)
    # L4 AGGRESSIVE also moves VALU/SALU
    assert optlevel.policy(4).reorder_alu is True
    assert optlevel.policy(3).reorder_alu is False
    # out-of-range clamps into the implemented range (max == AGGRESSIVE)
    assert optlevel.policy(99).level is optlevel.OptLevel.AGGRESSIVE
    assert optlevel.policy(-5).level is optlevel.OptLevel.CONSERVATIVE
    # default is BALANCED (preserves the validated current behavior)
    assert optlevel.DEFAULT is optlevel.OptLevel.BALANCED


def test_l4_valu_cannot_cross_address_consumer():
    # RAW: a v_* that computes a VGPR a later buffer_load uses as its address
    # must NOT be movable past that load. The dep-graph legal window enforces it.
    from reorder.editor import RegionEditor
    src = """.text
k:
loop:
  v_add_u32 v5, v6, v7
  v_mul_u32_u24 v8, v5, v9
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, v5, s[4:7], 0 offen lds
  v_add_u32 v10, v11, v12
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
    instrs = _instrs(prog)
    vadd = next(ln for ln in instrs if ln.opcode == "v_add_u32" and "v5" in ln.operands[0])
    bload = next(ln for ln in instrs if (ln.opcode or "").startswith("buffer_load"))
    # legal window of the v_add (producer of v5) must end strictly before the load
    lo, hi, _ = ed._block_insert_range(ed.unit(vadd.idx))
    load_pos = ed.order.index(bload.idx)
    assert hi <= load_pos, (hi, load_pos)   # cannot be placed at/after the load
    # sinking VALU as far as legal must keep v_add before the buffer_load
    ed.compact_kind(Kind.VALU, earliest=False)
    assert ed.order.index(vadd.idx) < ed.order.index(bload.idx)


def test_vcc_carry_chain_and_cmpx_fence_modeling():
    # carry-out (v_add_co) -> vcc reader (v_cndmask) must carry a RAW edge via
    # vcc, even though vcc is implicit; v_cmpx (writes exec) is a fence.
    from reorder.depgraph import DepGraph
    from isa.gfx942 import classify as cls
    assert cls.writes_vcc("v_add_co_u32") and cls.reads_vcc("v_cndmask_b32")
    assert "vcc" in cls.implicit_defs("v_add_co_u32", [])
    assert "vcc" in cls.implicit_uses("v_cndmask_b32", [])
    assert cls.writes_exec("v_cmpx_lt_u32", ["v0", "v1"])
    src = """.text
k:
  v_add_co_u32 v5, vcc, v1, v2
  v_mul_f32 v9, v3, v4
  v_cndmask_b32 v8, v9, v10, vcc
  v_cmpx_lt_u32 v0, v1
  v_mov_b32 v20, v21
  s_endpgm
"""
    prog, t = _load(src)
    lines = _instrs(prog)
    g = DepGraph.build(lines, t)
    addco = next(ln for ln in lines if ln.opcode == "v_add_co_u32")
    cnd = next(ln for ln in lines if ln.opcode == "v_cndmask_b32")
    cmpx = next(ln for ln in lines if ln.opcode == "v_cmpx_lt_u32")
    assert cnd.idx in g.succs(addco.idx)          # vcc RAW: add_co -> cndmask
    assert g.is_fence(cmpx.idx)                    # v_cmpx is a scheduling fence


def test_mfma_read_latency_min_distance_constraint():
    # an MFMA-write -> non-MFMA-read RAW edge carries a minimum position distance
    # AUTO-CALIBRATED from the seed's own tightest spacing for that MFMA opcode;
    # the consumer cannot be hoisted closer than that.
    from reorder.depgraph import DepGraph
    # seed places the consumer 4 slots after its producer MFMA -> calibrated == 4
    src = """.text
k:
loop:
  v_mfma_f32_16x16x32_fp8_fp8 v[36:39], a[0:1], a[2:3], v[36:39]
  v_mfma_f32_16x16x32_fp8_fp8 v[40:43], a[4:5], a[6:7], v[40:43]
  v_mov_b32 v60, v61
  v_mov_b32 v62, v63
  v_pk_fma_f32 v[52:53], v[4:5], v[36:37], v[52:53]
  s_endpgm
"""
    prog, t = _load(src)
    lines = [ln for ln in prog.lines if ln.is_instr]
    g = DepGraph.build(lines, t)
    mfma = next(ln for ln in lines if "v[36:39]" in (ln.operands[0] if ln.operands else ""))
    cons = next(ln for ln in lines if ln.opcode == "v_pk_fma_f32")
    gap = g.by_iid[cons.idx].pos - g.by_iid[mfma.idx].pos
    assert g.dist(mfma.idx, cons.idx) == gap == 4         # seed-derived latency
    # MFMA->MFMA accumulation stays distance 1 (pipelined, not latency-bound)
    m2 = next(ln for ln in lines if "v[40:43]" in (ln.operands[0] if ln.operands else ""))
    assert g.dist(mfma.idx, m2.idx) == 1
    # consumer's legal window starts >= producer.pos + latency (cannot be adjacent)
    lo, _ = g.legal_window(cons.idx)
    assert lo >= g.by_iid[mfma.idx].pos + gap


def test_non_loop_region_compact_then_cfg_verifies():
    # the editor is region-generic: reordering a NON-loop region (prologue) and
    # recomputing the whole kernel still verifies.
    from reorder.editor import RegionEditor
    src = open(SHADER).read()
    prog, t = _load(src)
    ref = parser.parse(src)
    pro = [r for r in regions.analyze(prog, t).regions if r.kind.value == "prologue"][0]
    ed = RegionEditor(prog, t, pro, treat_waitcnt_as_fence=False)
    d = ed.compact_kind(Kind.VMEM_LOAD, earliest=True)
    assert d.changed                                  # prologue actually reordered
    ed.materialize()
    waitcnt.recompute_cfg(prog, t, opt_level=1)
    res = Verifier(t, reference=ref,
                   analysis=regions.analyze(prog, t)).verify(prog)
    assert res.ok, res.violations[:6]


def test_span_editor_seals_loop_body():
    # a cross-region span editor pins each loop body's first/last instr as fences
    # so no unit crosses into/out of the loop (execution-count safety). A prologue
    # vmem_load therefore CANNOT be moved before a loop-body instruction.
    from reorder.editor import span_editor
    src = open(SHADER).read()
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    pro = [r for r in a.regions if r.kind.value == "prologue"][0]
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = span_editor(prog, t, [pro, loop], treat_waitcnt_as_fence=False)
    loop_body = [ln.idx for ln in ed.instr_lines
                 if loop.line_start <= ln.idx <= loop.line_end]
    assert loop_body[0] in ed._fences and loop_body[-1] in ed._fences
    # pick a movable prologue vmem_load and a loop-body instruction
    pro_loads = [i for i in ed.order
                 if ed.kind_of(i) is Kind.VMEM_LOAD and i < loop_body[0]
                 and i not in ed._fences]
    assert pro_loads, "expected a movable prologue vmem_load"
    target_in_loop = loop_body[len(loop_body) // 2]
    d = ed.move_before(pro_loads[-1], target_in_loop, strict=False)
    assert not d.changed                              # blocked by the loop seal
    assert ed.is_legal()


def test_recompute_cfg_whole_kernel_verifies():
    # whole-kernel multi-region recompute (prologue+loop+epilogue) with the
    # boundary counter contract produces a verifiable kernel.
    src = open(SHADER).read()
    prog, t = _load(src)
    ref = parser.parse(src)
    waitcnt.recompute_cfg(prog, t, opt_level=1)
    a = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a).verify(prog)
    assert res.ok, res.violations[:6]


def test_recompute_cfg_boundary_contract_fixes_epilogue():
    # isolated per-region recompute UNDER-syncs the epilogue (its ds_read/barrier
    # depend on lds-loads issued inside the loop, invisible out of scope); the
    # cross-region boundary contract in recompute_cfg fixes it.
    src = open(SHADER).read()
    ref = parser.parse(src)

    # (a) per-region in isolation -> epilogue LDS round-trip / fence violations
    prog_iso, t = _load(src)
    a = regions.analyze(prog_iso, t)
    for r in sorted(a.regions, key=lambda x: x.line_start):
        waitcnt.recompute(prog_iso, t, region=r, opt_level=1)
    res_iso = Verifier(t, reference=ref,
                       analysis=regions.analyze(prog_iso, t)).verify(prog_iso)
    assert not res_iso.ok                       # isolated recompute is unsafe

    # (b) recompute_cfg threads the loop-exit scoreboard into the epilogue
    prog_cfg, t2 = _load(src)
    waitcnt.recompute_cfg(prog_cfg, t2, opt_level=1)
    res_cfg = Verifier(t2, reference=ref,
                       analysis=regions.analyze(prog_cfg, t2)).verify(prog_cfg)
    assert res_cfg.ok, res_cfg.violations[:6]


def test_mfma_latency_calibrated_to_three_on_real_kernel():
    # the real hand-tuned kernel's tightest 16x16x32 MFMA -> v_pk_fma gap is 3,
    # so the auto-calibration recovers exactly the HW-validated latency == 3.
    from reorder.editor import RegionEditor
    src = open(SHADER).read()
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
    fp8 = [(aa, bb, d) for aa, bb, d in ed.graph.latency_edges()
           if (ed._line_of[aa].opcode or "").startswith("v_mfma")]
    assert fp8 and min(d for _, _, d in fp8) == 3


def test_l4_valu_hoist_respects_mfma_latency_real_kernel():
    # on the real kernel, hoisting VALU must keep every MFMA-write -> non-MFMA
    # consumer at >= the latency distance (the repair fixes gaps a multi-unit
    # hoist would otherwise collapse). Result must be dep-order legal.
    from reorder.editor import RegionEditor
    src = open(SHADER).read()
    prog, t = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
    ed.compact_kind(Kind.VALU, earliest=True)
    pos = {iid: i for i, iid in enumerate(ed.order)}
    for a_, b_, d in ed.graph.latency_edges():
        assert pos[b_] - pos[a_] >= d, (a_, b_, d, pos[b_] - pos[a_])
    assert ed.is_legal()


def test_l4_reorder_valu_salu_real_kernel_verifies():
    # moving VALU and SALU on the real kernel stays correct (verifier is the cull).
    from reorder.editor import RegionEditor
    src = open(SHADER).read()
    for kind in (Kind.VALU, Kind.SALU):
        prog, t = _load(src)
        ref, _ = _load(src)
        a = regions.analyze(prog, t)
        loop = [r for r in a.regions if r.kind.value == "loop"][0]
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
        ed.compact_kind(kind, earliest=True)
        ed.materialize()
        waitcnt.recompute(prog, t, region=loop, opt_level=1)
        a2 = regions.analyze(prog, t)
        assert Verifier(t, reference=ref, analysis=a2).verify(prog).ok, kind


def test_compact_kind_preserves_correctness_and_order():
    # hoisting loads on the real kernel keeps it verifiable and preserves the
    # loads' relative order (stable slide, not a scatter).
    from reorder.editor import RegionEditor
    src = open(SHADER).read()
    prog, t = _load(src)
    ref, _ = _load(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
    before = [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD]
    ed.compact_kind(Kind.VMEM_LOAD, earliest=True)
    after = [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD]
    assert before == after, "relative order of loads must be preserved"
    ed.materialize()
    waitcnt.recompute(prog, t, region=loop, opt_level=2)
    a2 = regions.analyze(prog, t)
    assert Verifier(t, reference=ref, analysis=a2).verify(prog).ok


def _barrier_vm(instrs, t, m, barrier_band_scoped):
    need = waitcnt.compute_waits_loop(instrs, t, lds_model=m,
                                      barrier_band_scoped=barrier_band_scoped)
    bar = next(ln for ln in instrs if (ln.opcode or "").lower() == "s_barrier")
    return need.get(bar.idx, {}).get("vm")


def test_optlevel_barrier_fence_l0_tighter_than_l1():
    # L0 (drain-all) must give a tighter-or-equal barrier vmcnt than L1
    # (band look-ahead), which keeps the unread bands' prefetch in flight.
    src = """.text
k:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 0x100, s2
  s_add_u32 s4, 0x100, s3
loop:
  s_waitcnt lgkmcnt(0)
  s_barrier
  ds_read_b64 v[10:11], v20 offset:0
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s4
  buffer_load_dword v2, s[4:7], 0 offen lds
  s_cbranch_scc0 loop
  s_endpgm
"""
    prog, t = _load(src)
    instrs = _instrs(prog)
    m = build_lds_model(instrs, t)
    vm_l0 = _barrier_vm(instrs, t, m, barrier_band_scoped=False)
    vm_l1 = _barrier_vm(instrs, t, m, barrier_band_scoped=True)
    assert vm_l0 is not None and vm_l1 is not None
    assert vm_l1 >= vm_l0, (vm_l1, vm_l0)


def test_optlevel_real_kernel_l0_and_l1_both_verify():
    src = open(SHADER).read()
    for level in (0, 1):
        prog, t = _load(src)
        ref, _ = _load(src)
        a = regions.analyze(prog, t)
        loop = [r for r in a.regions if r.kind.value == "loop"][0]
        waitcnt.recompute(prog, t, region=loop, opt_level=level)
        a2 = regions.analyze(prog, t)
        res = Verifier(t, reference=ref, analysis=a2).verify(prog)
        assert res.ok, (level, res.violations[:5])


def test_optlevel_real_kernel_l0_tighter_barrier_vm():
    # On the real triple-buffered kernel, L0's barrier vmcnt must be <= L1's at
    # every barrier (L0 drains all bands, L1 only the read band).
    src = open(SHADER).read()

    def barrier_vms(level):
        prog, t = _load(src)
        a = regions.analyze(prog, t)
        loop = [r for r in a.regions if r.kind.value == "loop"][0]
        waitcnt.recompute(prog, t, region=loop, opt_level=level)
        lines = [ln for ln in prog.lines if ln.kind is LineKind.INSTR and ln.opcode]
        out = []
        for i, ln in enumerate(lines):
            if (ln.opcode or "").lower() == "s_barrier" and i > 0:
                raw = lines[i - 1].raw
                if "vmcnt(" in raw:
                    out.append(int(raw.split("vmcnt(")[1].split(")")[0]))
        return out

    l0, l1 = barrier_vms(0), barrier_vms(1)
    assert l0 and l1 and len(l0) == len(l1)
    assert all(a <= b for a, b in zip(l0, l1)), (l0, l1)
    assert any(a < b for a, b in zip(l0, l1)), (l0, l1)   # at least one is looser
