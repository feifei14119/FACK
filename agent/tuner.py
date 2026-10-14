"""M7 meta-layer entrypoint: tie knowledge (navigate) + fixed-logic search
(adjudicate) into one before -> during -> after loop.

  BEFORE  seed_search_plan(context)        -> prior specs (what to try first)
  DURING  search(seed, ev, extra_specs=...) -> fixed logic gates by GFLOPS+Verifier
  AFTER   log each trial + induce_and_save   -> skills evolve (with confidence gate)

The inner search stays pure/reproducible; this layer is low-frequency. Knowledge
NEVER adjudicates legality -- see proj/knowledge_agent_design.md §2.
"""
from __future__ import annotations

from typing import Dict, Optional

from search.driver import search

from . import knowledge as kn


def tune(seed_src: str, evaluator, context: Dict, *,
         store: str = kn.DEFAULT_STORE, learn: bool = True, **search_kw):
    """Run a knowledge-seeded search for a kernel described by ``context``
    (e.g. ``{"arch":"gfx942","loop_kind":"mfma_dense","bottleneck":"compute",
    "kernel":"fp8gemm","shape":"k4096","scenario":"hand_tuned"}``).

    Returns ``(SearchResult, plan)``. With ``learn=True`` the trials are logged
    and skills re-induced so the store improves after every run."""
    plan = kn.seed_search_plan(context, store)
    res = search(seed_src, evaluator, extra_specs=plan["specs"], **search_kw)

    if learn and res.baseline_tflops:
        for t in res.trials:
            if t.spec is None or t.spec.get("kind") == "ladder":
                continue
            kn.log_experiment({
                "kernel": context.get("kernel"), "shape": context.get("shape"),
                "arch": context.get("arch"), "loop_kind": context.get("loop_kind"),
                "scenario": context.get("scenario"),
                "bottleneck": (res.direction.bottleneck if res.direction
                               else context.get("bottleneck")),
                "transform": _jsonable(t.spec),
                "baseline_tflops": res.baseline_tflops,
                "tflops": t.tflops, "correct": t.correct,
            }, store)
        kn.induce_and_save(store)
    return res, plan


def _jsonable(spec: Dict) -> Dict:
    """Convert a build_candidate spec (may hold a Weights dataclass) into a
    JSON-serialisable form for the experiments log."""
    out = dict(spec)
    w = out.get("weights")
    if w is not None and not isinstance(w, dict):
        out["weights"] = {k: getattr(w, k) for k in
                          ("critical_path", "latency", "load_hoist", "reg_pressure")
                          if hasattr(w, k)}
    return out
