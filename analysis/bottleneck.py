"""Classify aggregated ATT stats into a bottleneck + next-round direction hints.

Input: the dict from analysis.perf.aggregate(). Output: a ``direction`` dict that
feeds the M6 search / M7 agent -- which dimension dominates stalls and which edit
operators are worth trying next (e.g. distribute_evenly on a region).
"""
from __future__ import annotations

from typing import Dict

# bottleneck dimension -> concrete next-round hints for the reorder engine
_HINTS = {
    "lds": [
        "interleave ds_read into MFMA gaps: distribute_evenly(loop, DS_READ)",
        "consider double-buffering LDS to hide ds_read latency",
    ],
    "memory": [
        "overlap global loads with MFMA: distribute_evenly(loop, VMEM_LOAD)",
        "issue loads earlier / relax vmcnt so MFMA is not load-blocked",
    ],
    "scalar_mem": [
        "hoist s_load earlier in the prologue; coalesce scalar loads",
    ],
    "scalar": [
        "scalar-ALU bound: reduce redundant address math / s_* in the loop",
    ],
    "compute": [
        "compute(MFMA/VALU)-bound: limited reorder gains; check MFMA packing/occupancy",
    ],
    "flow": [
        "control-flow overhead: check loop trip count / branch density",
    ],
    "latency": [
        "latency-bound with no single hot dimension: raise ILP, "
        "distribute_evenly fillers across more MFMA gaps",
    ],
}


# A real dimension is the bottleneck only if it holds at least this share of the
# INFORMATIVE stall cycles; otherwise the stalls are diffuse -> generic latency.
_DOMINANCE = 0.40


def classify(counters: Dict, schema: Dict = None) -> Dict:
    """Return ``{"bottleneck", "share", "hints", "stats", ...}``.

    Heuristic: the dimension with the largest share of the **informative** stall
    cycles is the bottleneck; very diffuse stalls fall back to 'latency'.

    M6b validation finding (proj/if/direction_signal_validation.md): the ATT
    ``none`` bucket holds ~60% of stall cycles on the GEMM core loop, so a share
    taken over the *grand* total structurally pins every schedule to the
    'latency' fallback (no real dimension can clear 40% of a none-inflated
    total) -- the signal then carries ZERO discriminative information. Computing
    the share over informative dimensions only (dropping ``none``) recovers a
    signal that varies with the schedule (seed/even -> memory, hoist/sink ->
    compute) and is reasonably stable when voted over a few captures. The raw
    ``none`` fraction is still reported for transparency.
    """
    by_dim_stall = counters.get("by_dimension_stall", {}) or {}
    total = counters.get("total_stall", 0) or 0
    informative = {d: s for d, s in by_dim_stall.items() if d != "none" and s > 0}
    info_total = sum(informative.values())

    base = {
        "stats": dict(by_dim_stall),
        "total_stall": total,
        "informative_stall": info_total,
        "none_fraction": round((total - info_total) / total, 3) if total else 0.0,
    }
    if not informative or info_total == 0:
        return dict(base, bottleneck="none", share=0.0, hints=[])

    top_dim, top_stall = max(informative.items(), key=lambda kv: kv[1])
    share = top_stall / info_total            # share of INFORMATIVE stalls
    bottleneck = top_dim if share >= _DOMINANCE else "latency"

    return dict(base, bottleneck=bottleneck, share=round(share, 3),
                hints=_HINTS.get(bottleneck, _HINTS["latency"]))
