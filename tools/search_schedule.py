"""L3 = HW-in-the-loop schedule autotuner.

Searches the space of L2 per-instruction reorder transforms (kind x direction x
composition/order) applied to the current (already-optimized) kernel as seed:
for each candidate it static-verifies, builds the .co, runs gemm.exe best/median-
of-N on the real GPU, and ranks by correctness then median GFLOPS. Emits the
fastest correct schedule and a reproducible recipe.

  python3.8 tools/search_schedule.py [--k 8192] [--runs 12] [--out best.s]

Each candidate = recompute(opt_level=1 band-scoped) + forced-nop on top of an
ordered list of compact_kind ops; the winner is an L2-class schedule (see
reorder.optlevel: L3 SEARCH realizes an L2 product).
"""
import os
import subprocess
import sys
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parser, regions, emitter, waitcnt
from reorder.editor import RegionEditor
from reorder.verifier import Verifier
from reorder.model import Kind
from isa.gfx942.target import Gfx942Target
from isa.gfx942.passes import ForcedNopPass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TC = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm")
SHADER = os.path.join(TC, "shader", "fp8gemm_blockscase_32mx1_32nx4.s")
CLANG = "/opt/rocm/llvm/bin/clang++"

L, R = Kind.VMEM_LOAD, Kind.DS_READ
# (name, [ (kind, earliest), ... ])  -- applied in order on one editor pass
RECIPES = [
    ("L1_no_reorder", []),
    ("hoist_load", [(L, True)]),
    ("sink_load", [(L, False)]),
    ("hoist_dsr", [(R, True)]),
    ("sink_dsr", [(R, False)]),
    ("hoist_load+hoist_dsr", [(L, True), (R, True)]),
    ("hoist_dsr+hoist_load", [(R, True), (L, True)]),
    ("hoist_load+sink_dsr", [(L, True), (R, False)]),
]


def build_candidate(src, ops):
    """Return (emitted_text, verify_ok). Applies ops then recompute(L1)+nop."""
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    ref = parser.parse(src)
    a = regions.analyze(prog, t)
    loop = [r for r in a.regions if r.kind.value == "loop"][0]
    if ops:
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
        for kind, earliest in ops:
            ed.compact_kind(kind, earliest=earliest)
        ed.materialize()
    waitcnt.recompute(prog, t, region=loop, opt_level=1)
    ForcedNopPass().run(prog, t)
    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    return emitter.emit(prog), res.ok


def build_co(s_path, co_path):
    b = subprocess.run([CLANG, "-x", "assembler", "-target", "amdgcn--amdhsa",
                        "--offload-arch=gfx942", s_path, "-o", co_path],
                       cwd=TC, capture_output=True, text=True)
    return b.returncode == 0


def run_once(co_path, k):
    """Swap in co_path as gemm.co and run gemm.exe once; return (passed, gflops)."""
    subprocess.run(["cp", co_path, os.path.join(TC, "gemm.co")])
    r = subprocess.run([os.path.join(TC, "gemm.exe"), "k=%d" % k],
                       cwd=TC, capture_output=True, text=True)
    out = r.stdout
    passed = "TEST PASSED" in out
    g = None
    for line in out.splitlines():
        if "gflops:" in line:
            try:
                g = float(line.split("gflops:")[1].split()[0])
            except (IndexError, ValueError):
                pass
            break
    return passed, g


def main():
    argv = sys.argv
    k = int(argv[argv.index("--k") + 1]) if "--k" in argv else 8192
    runs = int(argv[argv.index("--runs") + 1]) if "--runs" in argv else 12
    out = argv[argv.index("--out") + 1] if "--out" in argv else "/tmp/l3_best.s"
    src = open(SHADER).read()

    print("== L3 schedule search (k=%d, runs=%d, round-robin interleaved) ==" % (k, runs))
    # Phase 1: build + static-verify + compile each candidate to its own .co
    cands = []      # (name, ops, text, co_path)
    for name, ops in RECIPES:
        text, ok = build_candidate(src, ops)
        if not ok:
            print("  %-22s SKIP (verify failed)" % name)
            continue
        s_path = "/tmp/_l3_%s.s" % name.replace("+", "_")
        co_path = "/tmp/_l3_%s.co" % name.replace("+", "_")
        with open(s_path, "w") as f:
            f.write(text)
        if not build_co(s_path, co_path):
            print("  %-22s BUILD FAILED" % name)
            continue
        cands.append((name, ops, text, co_path))

    # Phase 2: round-robin -- each round runs every candidate once, so GPU
    # clock/thermal drift biases all candidates equally (not one per block).
    samples = {c[0]: [] for c in cands}
    passes = {c[0]: 0 for c in cands}
    for _ in range(runs):
        for name, ops, text, co_path in cands:
            ok, g = run_once(co_path, k)
            if ok:
                passes[name] += 1
            if g is not None:
                samples[name].append(g)

    rows = []
    for name, ops, text, co_path in cands:
        g = samples[name]
        med = statistics.median(g) if g else 0.0
        rows.append((name, ops, passes[name], med, max(g) if g else 0.0, text))
        print("  %-22s PASS=%2d/%-2d  median=%8.1f  best=%8.1f" %
              (name, passes[name], runs, med, max(g) if g else 0.0))

    correct = [r for r in rows if r[2] == runs]
    correct.sort(key=lambda r: r[3], reverse=True)
    base = next((r[3] for r in rows if r[0] == "L1_no_reorder"), 0.0)
    print("\n== ranking (correct only, by median GFLOPS; baseline=L1 %.1f) ==" % base)
    for i, (name, ops, p, med, best, _) in enumerate(correct):
        delta = (med / base - 1.0) * 100 if base else 0.0
        print("  %d. %-22s median=%8.1f (%+5.1f%% vs L1) best=%8.1f" %
              (i + 1, name, med, delta, best))

    if correct:
        win = correct[0]
        with open(out, "w") as f:
            f.write(win[5])
        gain = (win[3] / base - 1.0) * 100 if base else 0.0
        recipe = " ; ".join("compact_kind(%s, earliest=%s)" % (kd.value, e)
                            for kd, e in win[1]) or "(none = L1)"
        print("\nWINNER: %s  median=%.1f (%+.1f%% vs L1)  -> %s" %
              (win[0], win[3], gain, out))
        print("recipe: %s" % recipe)
        # noise-aware verdict: noise floor = dispersion of L1's OWN repeated runs
        # (coefficient of variation). A win is meaningful only if it clears it.
        l1 = next((samples[r[0]] for r in rows if r[0] == "L1_no_reorder"), [])
        if len(l1) >= 2 and base:
            cov = (statistics.pstdev(l1) / base) * 100
            if gain <= cov:
                print("VERDICT: within measurement noise (L1 run-to-run CoV=%.1f%%);"
                      " on this already-tuned kernel no reorder RELIABLY beats L1."
                      " Re-run / lock GPU clocks to resolve." % cov)
            else:
                print("VERDICT: %s gain %.1f%% > L1 noise floor CoV=%.1f%%"
                      " (still modest -- confirm with more runs)." % (win[0], gain, cov))

    # restore the repo's gemm.co from the shader
    subprocess.run([CLANG, "-x", "assembler", "-target", "amdgcn--amdhsa",
                    "--offload-arch=gfx942", SHADER, "-o", os.path.join(TC, "gemm.co")],
                   cwd=TC, capture_output=True)


if __name__ == "__main__":
    main()
