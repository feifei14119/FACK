"""M6b: validate the reliability of EvalResult.direction before wiring it into
the M6c search loop.

The search loop will trust ``direction.bottleneck`` to pick the next edit
operator. Before building on it we must answer three questions on real HW:

  1. STABILITY  -- is the signal repeatable? Re-capture the SAME binary R times;
                   does bottleneck / per-dimension stall share stay put, or does
                   ATT sampling noise flip it run-to-run?
  2. DISCRIMINATION -- do genuinely different schedules (seed / hoist / sink /
                   scrambled even-distribute) produce DIFFERENT stall profiles?
  3. CORRELATION -- does a worse stall profile actually track worse GFLOPS?
                   (more total stall / a hotter dimension <-> lower perf)

It also reports an ALTERNATIVE classification that drops the non-informative
``none`` dimension from the share denominator -- on this kernel ``none`` holds
~60% of stall cycles, which structurally pins the current classifier to the
"latency" fallback (share < 40% of a none-inflated total). The validation
quantifies whether informative-only shares discriminate better.

Usage (real GPU + ROCm required):
  python3.8 tools/validate_direction.py [--k 4096] [--loop 20] \
      [--repeats 5] [--perf-repeats 3] [--out /tmp/direction_validation.json]
"""
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import bottleneck as _bn
from analysis import perf as _perf
from harness.evaluator import GpuTestcaseEvaluator
from isa.gfx942.target import Gfx942Target

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm")
MK = os.path.join(HERE, "tools", "make_candidate.py")

# (name, make_candidate argv) -- a small matrix with known schedule differences.
CANDIDATES = [
    ("seed_L1", ["cfg", "{out}", "--opt", "1"]),
    ("hoist_L2", ["level", "2", "{out}", "--reorder-kind", "vmem_load",
                  "--reorder-dir", "hoist"]),
    ("sink_L2", ["level", "2", "{out}", "--reorder-kind", "vmem_load",
                 "--reorder-dir", "sink"]),
    ("even_scramble", ["even_distribute", "{out}", "--opt", "1"]),
]


def _arg_int(argv, flag, default):
    return int(argv[argv.index(flag) + 1]) if flag in argv else default


def _arg_str(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def _build(name, argv_tmpl):
    out = os.path.join("/tmp", "vd_%s.s" % name)
    argv = [a.format(out=out) for a in argv_tmpl]
    p = subprocess.run([sys.executable, MK] + argv, capture_output=True, text=True)
    ok = "verify ok=True" in p.stderr
    return out, ok, p.stderr.strip().splitlines()[-3:]


def _informative_classify(by_dim_stall):
    """Bottleneck over INFORMATIVE stalls only (drop 'none'/'flow'-less noise):
    share is computed against the sum of meaningful-dimension stalls, so a real
    hot spot is not masked by the large 'none' bucket."""
    info = {d: s for d, s in by_dim_stall.items() if d != "none" and s > 0}
    tot = sum(info.values())
    if not info or tot == 0:
        return {"bottleneck": "none", "share": 0.0, "stats": dict(info)}
    top_d, top_s = max(info.items(), key=lambda kv: kv[1])
    share = top_s / tot
    return {"bottleneck": top_d if share >= 0.40 else "latency",
            "share": round(share, 3), "stats": dict(info)}


def _cv(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = statistics.mean(xs)
    return (statistics.pstdev(xs) / m) if m else 0.0


def _mode_freq(xs):
    if not xs:
        return None, 0.0
    counts = {}
    for x in xs:
        counts[x] = counts.get(x, 0) + 1
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0], best[1] / len(xs)


def _spearman(xs, ys):
    """Rank correlation (no scipy). Returns None if <3 points."""
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def main():
    argv = sys.argv
    k = _arg_int(argv, "--k", 4096)
    loop = _arg_int(argv, "--loop", 20)
    repeats = _arg_int(argv, "--repeats", 5)
    perf_repeats = _arg_int(argv, "--perf-repeats", 3)
    out_json = _arg_str(argv, "--out", "/tmp/direction_validation.json")

    target = Gfx942Target()
    schema = target.perf_counter_schema()
    ev = GpuTestcaseEvaluator(TC, target=target, total_loop=loop, k=k)

    results = []
    for name, tmpl in CANDIDATES:
        spath, built_ok, tail = _build(name, tmpl)
        print("\n### %s  (build ok=%s)" % (name, built_ok))
        if not built_ok or not os.path.exists(spath):
            print("   skip: build failed: %s" % tail)
            continue
        try:
            ev.assemble(spath)
        except Exception as exc:  # noqa: BLE001
            print("   skip: assemble failed: %s" % exc)
            continue
        correct = ev.check_correctness(spath)
        if correct is False:
            print("   skip: INCORRECT")
            continue

        gflops_runs = []
        for _ in range(perf_repeats):
            _t, g = ev.measure_perf(spath)
            if g is not None:
                gflops_runs.append(g)
        gflops = statistics.median(gflops_runs) if gflops_runs else None

        caps = []
        for _ in range(repeats):
            try:
                ev.dump_counters(spath, os.path.join(TC, "att"))
                counters = _perf.parse(os.path.join(TC, "att"), schema)
            except Exception as exc:  # noqa: BLE001
                print("   capture failed: %s" % exc)
                continue
            cur = _bn.classify(counters, schema)
            inf = _informative_classify(counters.get("by_dimension_stall", {}))
            caps.append({
                "total_stall": counters.get("total_stall", 0),
                "n_inst": counters.get("n_inst", 0),
                "by_dim": counters.get("by_dimension_stall", {}),
                "bottleneck_cur": cur.get("bottleneck"),
                "share_cur": cur.get("share"),
                "bottleneck_info": inf.get("bottleneck"),
                "share_info": inf.get("share"),
            })

        if not caps:
            print("   no captures")
            continue
        bn_cur_mode, bn_cur_freq = _mode_freq([c["bottleneck_cur"] for c in caps])
        bn_inf_mode, bn_inf_freq = _mode_freq([c["bottleneck_info"] for c in caps])
        stall_cv = _cv([c["total_stall"] for c in caps])
        med_total = statistics.median([c["total_stall"] for c in caps])
        # median informative share of the most-common informative bottleneck
        rec = {
            "name": name, "correct": correct, "gflops": gflops,
            "gflops_runs": gflops_runs,
            "median_total_stall": med_total, "total_stall_cv": round(stall_cv, 3),
            "bottleneck_cur": bn_cur_mode, "bottleneck_cur_stability": round(bn_cur_freq, 2),
            "bottleneck_info": bn_inf_mode, "bottleneck_info_stability": round(bn_inf_freq, 2),
            "captures": caps,
        }
        results.append(rec)
        print("   perf=%s GFLOPS  median_total_stall=%d  stall_cv=%.2f" %
              (("%.0f" % gflops) if gflops else "?", med_total, stall_cv))
        print("   bottleneck[current ]=%s (stable %.0f%%)" % (bn_cur_mode, 100 * bn_cur_freq))
        print("   bottleneck[informat]=%s (stable %.0f%%)" % (bn_inf_mode, 100 * bn_inf_freq))

    # cross-candidate correlation: perf vs stall (expect negative)
    named = [r for r in results if r["gflops"] is not None]
    print("\n==================== SUMMARY ====================")
    print("%-16s %10s %14s %8s %-12s %-12s" %
          ("candidate", "GFLOPS", "med_stall", "cv", "bn[cur]", "bn[info]"))
    for r in sorted(named, key=lambda x: -(x["gflops"] or 0)):
        print("%-16s %10.0f %14d %8.2f %-12s %-12s" %
              (r["name"], r["gflops"], r["median_total_stall"], r["total_stall_cv"],
               r["bottleneck_cur"], r["bottleneck_info"]))
    if len(named) >= 3:
        perf = [r["gflops"] for r in named]
        stall = [r["median_total_stall"] for r in named]
        print("\nSpearman(perf, total_stall) = %s   (expect NEGATIVE: more stall -> less perf)"
              % _spearman(perf, stall))

    with open(out_json, "w") as f:
        json.dump({"k": k, "loop": loop, "repeats": repeats,
                   "results": results}, f, indent=2)
    print("\nwrote %s" % out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
