"""M6c: run the direction-guided search loop on the real testcase GPU.

Wires search.driver.search() to harness.evaluator.GpuTestcaseEvaluator on
testft/testcase. Measures the L1 baseline, votes the ATT ``direction`` (5
captures), prioritises operators by the voted bottleneck (fixed-ladder fallback
when low-confidence), builds + measures each candidate, and reports the fastest
CORRECT schedule that clears the noise margin.

  python3.8 tools/search_loop.py [--k 4096] [--loop 20] [--perf-repeats 3] \
      [--captures 5] [--no-direction] [--margin 0.01] [--out best.s]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.evaluator import GpuTestcaseEvaluator
from isa import registry
from search.driver import search

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm")
SHADER = os.path.join(TC, "shader", "fp8gemm_blockscase_32mx1_32nx4.s")


def _i(argv, flag, d):
    return int(argv[argv.index(flag) + 1]) if flag in argv else d


def _f(argv, flag, d):
    return float(argv[argv.index(flag) + 1]) if flag in argv else d


def _s(argv, flag, d):
    return argv[argv.index(flag) + 1] if flag in argv else d


def main():
    argv = sys.argv
    k = _i(argv, "--k", 4096)
    loop = _i(argv, "--loop", 20)
    perf_repeats = _i(argv, "--perf-repeats", 3)
    captures = _i(argv, "--captures", 5)
    use_direction = "--no-direction" not in argv
    margin = _f(argv, "--margin", 0.01)
    out = _s(argv, "--out", "/tmp/search_best.s")

    seed_src = open(SHADER).read()
    ev = GpuTestcaseEvaluator(TC, target=registry.target_for_source(seed_src),
                              total_loop=loop, k=k)

    res = search(seed_src, ev, perf_repeats=perf_repeats,
                 direction_captures=captures, use_direction=use_direction,
                 noise_margin=margin)

    print("== M6c search (k=%d, loop=%d, perf_repeats=%d) ==" % (k, loop, perf_repeats))
    if res.direction is not None:
        v = res.direction
        print("  direction vote: bottleneck=%s confidence=%.0f%% votes=%s trusted=%s"
              % (v.bottleneck, 100 * v.confidence, v.votes, v.trusted()))
    print("  baseline: %s TFLOPS" %
          (("%.2f" % res.baseline_tflops) if res.baseline_tflops else "?"))
    print("  trials:")
    for t in res.trials:
        print("    %-18s correct=%s tflops=%s %s%s" % (
            t.name, t.correct,
            ("%.2f" % t.tflops) if t.tflops else "?",
            "ACCEPTED" if t.accepted else "",
            (" [%s]" % t.note) if t.note else ""))
    gain = ((res.best_tflops / res.baseline_tflops - 1.0) * 100
            if (res.best_tflops and res.baseline_tflops) else 0.0)
    print("  WINNER: %s  %s TFLOPS  (%+.1f%% vs baseline)" % (
        res.best_name, ("%.2f" % res.best_tflops) if res.best_tflops else "?", gain))
    if res.best_path and os.path.exists(res.best_path):
        with open(res.best_path) as f:
            open(out, "w").write(f.read())
        print("  wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
