"""Mechanism A: tunable-weight list scheduler (architecture-agnostic).

A classic greedy list scheduler over the region DAG: at each step pick the
ready instruction with the highest weighted score. The *search dimension* is a
handful of weights, not a per-instruction plan -- heterogeneous gap placement
emerges naturally from the dependency structure + weights (this is how real
compilers schedule, and it generalizes across kernels).

The schedule is legal by construction within fence-bounded segments: an
instruction becomes ready only once all its in-segment predecessors are placed
(so every dependency edge a->b keeps a before b), and instructions never cross a
fence (barrier / exec-write / branch / existing waitcnt). Minimum-distance
(latency) edges are honoured best-effort by readiness time; the caller validates
the final order with ``graph.is_order_legal`` and the FixupPass pipeline repairs
any residual MFMA latency with ``s_nop``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from reorder.depgraph import DepGraph
from reorder.model import Kind


@dataclass
class Weights:
    """List-scheduler priority weights (the search knobs)."""

    critical_path: float = 1.0     # favour nodes on the longest dependency chain
    latency: float = 0.5           # issue long-latency producers (MFMA) early
    load_hoist: float = 0.0        # bonus for issuing VMEM loads early (overlap)
    neg_reg_pressure: float = 0.0  # penalise opening many new live values
    order_tiebreak: float = 1e-6   # keep original program order on ties (stable)


def _critical_path(graph: DepGraph, nodes: List[int]) -> Dict[int, int]:
    """Longest downstream path length (in edges) from each node, memoized."""
    succ = {i: [s for s in graph.succs(i) if s in set(nodes)] for i in nodes}
    cp: Dict[int, int] = {}

    def visit(i: int) -> int:
        if i in cp:
            return cp[i]
        cp[i] = 0  # guard against cycles (there should be none)
        best = 0
        for s in succ[i]:
            best = max(best, 1 + visit(s))
        cp[i] = best
        return best

    for i in nodes:
        visit(i)
    return cp


def _out_latency(graph: DepGraph, nodes: List[int]) -> Dict[int, int]:
    nodeset = set(nodes)
    return {i: max([graph.dist(i, s) for s in graph.succs(i) if s in nodeset] or [1])
            for i in nodes}


def _segments(order: List[int], fences: Set[int]) -> List[List[int]]:
    """Split into maximal runs of non-fence instructions (fences are pinned)."""
    segs: List[List[int]] = []
    cur: List[int] = []
    for i in order:
        if i in fences:
            if cur:
                segs.append(cur)
                cur = []
            segs.append([i])          # fence is its own singleton (pinned)
        else:
            cur.append(i)
    if cur:
        segs.append(cur)
    return segs


def schedule(graph: DepGraph, order0: List[int], fences: Set[int],
             weights: Optional[Weights] = None,
             kind_of=None) -> List[int]:
    """Return a new legal-by-construction order via weighted greedy scheduling.

    ``kind_of(iid) -> Kind`` is optional (only needed for ``load_hoist``)."""
    w = weights or Weights()
    cp = _critical_path(graph, order0)
    lat = _out_latency(graph, order0)
    orig_idx = {iid: k for k, iid in enumerate(order0)}

    def is_load(iid: int) -> bool:
        return kind_of is not None and kind_of(iid) is Kind.VMEM_LOAD

    out: List[int] = []
    for seg in _segments(order0, fences):
        if len(seg) == 1 and seg[0] in fences:
            out.append(seg[0])
            continue
        segset = set(seg)
        unsched = set(seg)
        placed: Set[int] = set()
        # in-segment predecessor count drives readiness
        pred_in = {i: {p for p in graph.preds(i) if p in segset} for i in seg}
        live = 0
        while unsched:
            ready = [i for i in seg if i in unsched and pred_in[i] <= placed]
            if not ready:               # blocked (shouldn't happen in a DAG) -> bail
                ready = [i for i in seg if i in unsched]

            def score(i: int) -> float:
                return (w.critical_path * cp[i]
                        + w.latency * lat[i]
                        + w.load_hoist * (1.0 if is_load(i) else 0.0)
                        + w.neg_reg_pressure * (-len(graph.succs(i)))
                        + w.order_tiebreak * (-orig_idx[i]))

            pick = max(ready, key=score)
            out.append(pick)
            placed.add(pick)
            unsched.discard(pick)
    return out


def schedule_phase(ed, weights: Optional[Weights] = None,
                   phase: Optional[int] = None) -> List[int]:
    """Schedule a RegionEditor's whole order, or only phase ``phase`` of it
    (``reorder.phases`` over the MFMA anchors) with everything outside that
    contiguous range kept in place. Cross-boundary dependencies stay satisfied
    by construction (outside nodes are all before or all after the range);
    cross-boundary latency distances are left to the caller's legality check."""
    base = list(ed.order)
    if phase is None:
        return schedule(ed.graph, base, ed._fences, weights, kind_of=ed.kind_of)
    from reorder import phases as _ph
    ph = _ph.split_phases(base, ed.anchors(Kind.MFMA))[int(phase)]
    mid = schedule(ed.graph, base[ph.lo:ph.hi + 1], ed._fences, weights,
                   kind_of=ed.kind_of)
    return base[:ph.lo] + mid + base[ph.hi + 1:]
