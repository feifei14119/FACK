"""Seed the M7 knowledge store from REAL measured experiments (no fabrication).

Logs the cold-start + search trials we measured on MI308X (2026-06, k=4096,
loop=20; see proj/if/coldstart_validation.md and tools/search_loop.py output)
into knowledge/engine/experiments.log, then runs ``induce_skills`` to generalise the
first skills, and adds one hand-authored INSIGHT skill (cross-iteration prefetch
is the dominant lever) that is qualitative rather than a per-transform delta.

  python3.8 tools/seed_knowledge.py [--reset]

Re-runnable. With --reset it truncates the log first so re-seeding is idempotent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn
from agent.knowledge import Skill

STORE = kn.DEFAULT_STORE
K = "fp8gemm_blockscase"
SHAPE = "k4096"

# (scenario, bottleneck, baseline, [(transform, tflops, correct), ...])
# All numbers are real medians from our HW runs.
RUNS = [
    # hand-tuned seed search (baseline 8.88, direction voted compute 5/5)
    ("hand_tuned", "compute", 8.88, [
        ({"kind": "listsched", "weights": {"critical_path": 1.5}}, 6.30, True),
        ({"kind": "compact", "reorder_kind": "vmem_load", "earliest": True}, 7.94, True),
        ({"kind": "compact", "reorder_kind": "vmem_load", "earliest": False}, 7.95, True),
        ({"kind": "listsched", "weights": {"load_hoist": 1.0}}, 6.50, True),
        ({"kind": "listsched", "weights": {"critical_path": 1.5, "latency": 1.0}}, 6.27, True),
    ]),
    # cold-start (memory sunk; baseline 7.45/7.47) -- engine recovery probes
    ("cold_start", "compute", 7.45, [
        ({"kind": "distribute_evenly", "kinds": ["vmem_load", "ds_read"]}, 7.43, True),
        ({"kind": "compact_both", "earliest": True}, 7.74, True),   # hoist load+ds_read
    ]),
    ("cold_start", "compute", 7.47, [
        ({"kind": "compact", "reorder_kind": "vmem_load", "earliest": True}, 7.26, True),
        ({"kind": "compact", "reorder_kind": "vmem_load", "earliest": False}, 7.31, True),
        ({"kind": "listsched", "weights": {"load_hoist": 1.0}}, 6.35, True),
        ({"kind": "listsched", "weights": {"critical_path": 1.5}}, None, False),
        ({"kind": "listsched", "weights": {"critical_path": 1.5, "latency": 1.0}}, None, False),
    ]),
]


def main():
    if "--reset" in sys.argv:
        p = kn._log_path(STORE)
        if os.path.exists(p):
            os.remove(p)
        d = kn._skills_dir(STORE)
        if os.path.isdir(d):
            for fn in os.listdir(d):
                os.remove(os.path.join(d, fn))

    for scenario, bottleneck, base, trials in RUNS:
        for transform, tflops, correct in trials:
            kn.log_experiment({
                "kernel": K, "shape": SHAPE, "arch": "gfx942",
                "loop_kind": "mfma_dense", "scenario": scenario,
                "bottleneck": bottleneck, "transform": transform,
                "baseline_tflops": base, "tflops": tflops, "correct": correct,
                "source": "MI308X 2026-06",
            }, STORE)

    induced = kn.induce_and_save(STORE)

    # Hand-authored qualitative insight (the dominant lever the engine can't yet
    # pull): kept as a candidate note -- navigation only.
    insight = Skill(
        id="insight-xiter-prefetch-dominant",
        statement="On mfma-dense GEMM, the dominant lever is cross-iteration "
                  "software-pipelined prefetch (~16%); single-loop-body reorder "
                  "recovers only ~4%. Until the engine adds cross-iteration "
                  "prefetch, on a cold kernel hoist loads+ds_read together "
                  "(compacting only loads can regress).",
        when={"arch": "gfx942", "loop_kind": "mfma_dense"},
        action={"note": "engine-gap: no cross-iteration prefetch; cold-start best "
                        "single-body move = hoist load+ds_read together",
                "specs": [{"kind": "compact", "reorder_kind": "vmem_load", "earliest": True},
                          {"kind": "compact", "reorder_kind": "ds_read", "earliest": True}]},
        evidence={"kernels": [K], "shapes": [SHAPE], "n_samples": 4,
                  "doc": "proj/if/coldstart_validation.md"},
        effect={"mean_delta": 0.039, "win_rate": "1/1", "note": "hoist vs cold +3.9%"},
        confidence=0.5,
        status="candidate",
    )
    kn.save_skill(insight, STORE)

    skills = kn.load_skills(STORE)
    print("== seeded knowledge store: %s ==" % STORE)
    print("experiments logged: %d" % len(kn.read_experiments(STORE)))
    print("skills: %d (induced %d + 1 insight)" % (len(skills), len(induced)))
    for s in sorted(skills, key=lambda x: (x.status != "trusted", -x.confidence)):
        verb = "prefer" if s.action.get("specs") and not s.action.get("avoid") else \
               ("avoid" if s.action.get("avoid") else "note")
        print("  [%-9s c=%.2f %-6s] %s" % (s.status, s.confidence, verb, s.statement[:84]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
