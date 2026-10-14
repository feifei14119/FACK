"""Cold-start demonstration: prove the engine RECOVERS performance on an
un-tuned (naively-scheduled) kernel, not just "ties" a hand-tuned seed.

We synthesise a *cold* kernel from the validated gemm seed by sinking every
memory op (vmem_load / ds_read) to its latest legal slot -- i.e. "load right
before you use it", the naive schedule a correctness-only kernel would have,
with NO compute/memory overlap. Then we let the fixed-logic engine re-spread
the memory ops back into the MFMA stream (distribute_evenly / compact-earliest)
and measure the recovery on real hardware.

  python3.8 tools/coldstart_demo.py [--k 4096] [--loop 20] [--repeats 3]

Reports median TFLOPS for: seed-L1 (reference), cold (sunk), and each recovery
transform, all numerically verified + Verifier-checked + HW-correctness-gated.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.evaluator import GpuTestcaseEvaluator
from isa.gfx942.passes import ForcedNopPass
from isa.gfx942.target import Gfx942Target
from reorder import emitter, parser, regions, waitcnt
from reorder.editor import RegionEditor
from reorder.model import Kind
from reorder.verifier import Verifier

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm")
SHADER = os.path.join(TC, "shader", "fp8gemm_blockscase_32mx1_32nx4.s")


def _loop(prog, t):
    return [r for r in regions.analyze(prog, t).regions if r.kind.value == "loop"][0]


def _finish(prog, t, ref, opt_level=1):
    loop = _loop(prog, t)
    waitcnt.recompute(prog, t, region=loop, opt_level=opt_level)
    ForcedNopPass().run(prog, t)
    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    return emitter.emit(prog), res.ok, res.violations


def build_seed_l1():
    prog = parser.parse(open(SHADER).read())
    t = Gfx942Target.from_program(prog)
    ref = parser.parse(open(SHADER).read())
    return _finish(prog, t, ref)


def build_cold():
    """Naive schedule: sink every memory op to its latest legal slot."""
    prog = parser.parse(open(SHADER).read())
    t = Gfx942Target.from_program(prog)
    ref = parser.parse(open(SHADER).read())
    ed = RegionEditor(prog, t, _loop(prog, t), treat_waitcnt_as_fence=False)
    ed.compact_kind(Kind.VMEM_LOAD, earliest=False)
    ed.compact_kind(Kind.DS_READ, earliest=False)
    if not ed.is_legal():
        return "", False, ["cold order illegal"]
    ed.materialize()
    return _finish(prog, t, ref)


def build_recover(transform):
    """Start from the cold (sunk) order, then re-spread via the engine."""
    prog = parser.parse(open(SHADER).read())
    t = Gfx942Target.from_program(prog)
    ref = parser.parse(open(SHADER).read())
    ed = RegionEditor(prog, t, _loop(prog, t), treat_waitcnt_as_fence=False)
    ed.compact_kind(Kind.VMEM_LOAD, earliest=False)
    ed.compact_kind(Kind.DS_READ, earliest=False)
    n_mfma = len(ed.anchors(Kind.MFMA))
    if transform == "distribute":
        ed.distribute_evenly(Kind.VMEM_LOAD, 0, n_mfma - 1)
        ed.distribute_evenly(Kind.DS_READ, 0, n_mfma - 1)
    elif transform == "hoist":
        ed.compact_kind(Kind.VMEM_LOAD, earliest=True)
        ed.compact_kind(Kind.DS_READ, earliest=True)
    if not ed.is_legal():
        return "", False, ["recover order illegal"]
    ed.materialize()
    return _finish(prog, t, ref)


def _i(argv, flag, d):
    return int(argv[argv.index(flag) + 1]) if flag in argv else d


def main():
    argv = sys.argv
    k = _i(argv, "--k", 4096)
    loop = _i(argv, "--loop", 20)
    repeats = _i(argv, "--repeats", 3)
    ev = GpuTestcaseEvaluator(TC, target=Gfx942Target(), total_loop=loop, k=k)

    cases = [
        ("seed_L1 (hand-tuned ref)", build_seed_l1),
        ("cold (memory sunk, naive)", build_cold),
        ("cold + distribute_evenly", lambda: build_recover("distribute")),
        ("cold + compact-earliest (hoist)", lambda: build_recover("hoist")),
    ]

    print("== cold-start demo (k=%d, loop=%d, repeats=%d) ==" % (k, loop, repeats))
    results = {}
    for name, builder in cases:
        text, ok, viol = builder()
        if not ok:
            print("  %-34s VERIFY-FAILED %s" % (name, viol[:1]))
            continue
        p = os.path.join("/tmp", "cold_%s.s" % name.split()[0])
        with open(p, "w") as f:
            f.write(text)
        vals, correct = [], None
        for _ in range(repeats):
            r = ev.evaluate(p, with_counters=False)
            if r.correct is False:
                correct = False
                break
            correct = r.correct
            if r.tflops is not None:
                vals.append(r.tflops)
        med = statistics.median(vals) if vals else None
        results[name] = (correct, med)
        print("  %-34s correct=%s  median=%s TFLOPS" % (
            name, correct, ("%.2f" % med) if med else "?"))

    ref = results.get("seed_L1 (hand-tuned ref)", (None, None))[1]
    cold = results.get("cold (memory sunk, naive)", (None, None))[1]
    if ref and cold:
        print("\n  cold vs hand-tuned seed: %+.1f%%" % ((cold / ref - 1) * 100))
        for name in ("cold + distribute_evenly", "cold + compact-earliest (hoist)"):
            v = results.get(name, (None, None))[1]
            if v:
                print("  %-34s: %+.1f%% vs cold, %+.1f%% vs seed" % (
                    name, (v / cold - 1) * 100, (v / ref - 1) * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
