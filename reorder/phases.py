"""Phase segmentation of a region by its MFMA/WMMA anchors.

A fused-attention core loop (e.g. MLA decode: GEMM-K -> softmax -> GEMM-V) has
WMMA-dense stretches separated by long anchor-free stretches. The slot model
(fill the gaps between consecutive anchors) fits the dense stretches; an
anchor-free stretch of hundreds of VALU/LDS ops is one meaningless "slot" and
needs the anchor-less DAG treatment instead (proj/mixed_loop_scheduling.md P1).

``split_phases`` cuts the region's current order into contiguous phases:
  * ``anchored``   -- a run of anchors whose consecutive gaps are all small
                      (plus short lead-in / tail fillers),
  * ``anchorless`` -- a gap between two anchors (or a region prefix / suffix)
                      longer than the threshold.
A region without anchors is a single anchorless phase. Pure function of the
order + anchor positions; no ISA knowledge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import List, Optional, Sequence

ANCHORED = "anchored"
ANCHORLESS = "anchorless"

MIN_GAP_THRESHOLD = 24     # a gap this long is never a plain slot
GAP_FACTOR = 3             # ... nor one this many times the typical slot


@dataclass
class Phase:
    index: int
    kind: str                      # ANCHORED | ANCHORLESS
    lo: int                        # first position in the region order (inclusive)
    hi: int                        # last position (inclusive)
    anchors: List[int] = field(default_factory=list)   # anchor iids inside

    @property
    def size(self) -> int:
        return self.hi - self.lo + 1


def gap_threshold(gaps: Sequence[int], threshold: Optional[int] = None) -> int:
    if threshold is not None:
        return threshold
    typical = median(gaps) if gaps else 0
    return max(MIN_GAP_THRESHOLD, int(GAP_FACTOR * typical))


def split_phases(order: Sequence[int], anchors: Sequence[int],
                 threshold: Optional[int] = None) -> List[Phase]:
    """Phases of ``order`` (iids) given the anchor iids (in order)."""
    n = len(order)
    if n == 0:
        return []
    if not anchors:
        return [Phase(0, ANCHORLESS, 0, n - 1)]
    pos = {iid: k for k, iid in enumerate(order)}
    ap = [pos[a] for a in anchors]
    gaps = [b - a - 1 for a, b in zip(ap, ap[1:])]
    thr = gap_threshold(gaps, threshold)

    spans = []                     # (kind, lo, hi)
    lead = ap[0]
    if lead > thr:
        spans.append((ANCHORLESS, 0, ap[0] - 1))
        start = ap[0]
    else:
        start = 0
    for k, g in enumerate(gaps):
        if g > thr:
            spans.append((ANCHORED, start, ap[k]))
            spans.append((ANCHORLESS, ap[k] + 1, ap[k + 1] - 1))
            start = ap[k + 1]
    tail = n - 1 - ap[-1]
    if tail > thr:
        spans.append((ANCHORED, start, ap[-1]))
        spans.append((ANCHORLESS, ap[-1] + 1, n - 1))
    else:
        spans.append((ANCHORED, start, n - 1))

    out: List[Phase] = []
    for kind, lo, hi in spans:
        inside = [order[p] for p in ap if lo <= p <= hi]
        out.append(Phase(len(out), kind, lo, hi, inside))
    return out
