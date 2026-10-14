"""End-to-end three-phase evaluation of ONE candidate .s through a client.

Wires the full evaluation contract (harness/evaluator.py) for the chosen client
(client/README.md):

    build -> correctness -> perf -> counter dump (optional) -> analysis

Phase 3 (``--counters``) asks the client's evaluator for a counter dump (for
exe-protocol clients: ATT via rocprofv2), aggregates per-dimension
stall cycles (analysis/perf.py) and classifies the
bottleneck + next-round hints (analysis/bottleneck.py). The ``direction`` it
prints is exactly what the M6 search / M7 agent consumes to choose the next edit
operator -- this tool closes that loop end-to-end.

  python3.8 tools/eval_candidate.py <candidate.s> --client poc_kl/fp8_blockscale_gemm \
      [--loop 20] [--counters] [--kernel NAME] -- m=2560 n=2560 k=256

Params after ``--`` are forwarded verbatim to the client. Without
``--counters`` it stops after phase 2. The traced kernel is auto-detected from
the candidate .s (``.amdhsa_kernel``); override with ``--kernel``.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client as _clients


def _arg_int(argv, flag, default):
    return int(argv[argv.index(flag) + 1]) if flag in argv else default


def _arg_str(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main():
    argv = sys.argv[1:]
    params = []
    if "--" in argv:
        sep = argv.index("--")
        params, argv = argv[sep + 1:], argv[:sep]
    spec = _arg_str(argv, "--client", None)
    if not argv or spec is None:
        print(__doc__)
        print("known clients: " + (", ".join(_clients.list_clients()) or "none"))
        return 2
    cand = argv[0]
    loop = _arg_int(argv, "--loop", 20)
    with_counters = "--counters" in argv
    kernel = _arg_str(argv, "--kernel", None)

    with open(cand) as f:
        src = f.read()
    try:
        cl = _clients.resolve(spec)
    except ValueError as exc:
        print("eval_candidate: {}".format(exc))
        return 2
    ev = cl.make_evaluator(seed_src=src, params=params, loop=loop, kernel=kernel)
    res = ev.evaluate(cand, with_counters=with_counters)

    print("== eval %s (client=%s, params=[%s], loop=%d) ==" % (
        os.path.basename(cand), cl.spec, " ".join(params), loop))
    print("  assembled : %s" % res.compiled)
    if not res.compiled:
        print("  error     : %s" % res.detail.get("error"))
        return 1
    print("  correct   : %s" % res.correct)
    if res.tflops is not None:
        print("  perf      : %.3f TFLOPS  (%.3f us)" % (res.tflops, res.time_us or 0.0))
    elif res.time_us is not None:
        print("  perf      : %.3f us" % res.time_us)

    if with_counters:
        if res.direction is None:
            print("  counters  : FAILED (%s)" % res.detail.get("counter_error"))
            return 1
        d = res.direction
        c = res.counters or {}
        print("  dump      : %s" % res.counter_dump_path)
        print("  insts     : %d  total_stall=%d" %
              (c.get("n_inst", 0), c.get("total_stall", 0)))
        print("\n== DIRECTION (phase-3 analysis -> search/agent) ==")
        print("  bottleneck: %s (%.0f%% of stalls)" %
              (d.get("bottleneck"), 100 * d.get("share", 0.0)))
        stats = sorted((d.get("stats") or {}).items(), key=lambda kv: kv[1], reverse=True)
        if stats:
            tot = sum(s for _, s in stats) or 1
            print("  stall by dimension:")
            for dim, s in stats:
                print("    %-12s %10d  (%.1f%%)" % (dim, s, 100 * s / tot))
        print("  next-round hints:")
        for h in d.get("hints", []):
            print("    - %s" % h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
