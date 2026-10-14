"""Cross-iteration prefetch RECOGNITION (read-only, architecture-agnostic).

The prefetch *schedule* of a software-pipelined kernel is fixed at design time
(prefetch-1 / prefetch-2 etc.) -- this module does NOT synthesise or change it.
It only RECOGNISES the existing prefetch so the rest of the engine can (a) compute
correct loop-carried ``s_waitcnt`` and (b) avoid scattering prefetch loads during
reorder (see ``RegionEditor(protect_prefetch=True)``).

A load is a *cross-iteration prefetch* when its result is consumed in a LATER
iteration -- i.e. the binding consumer sits BEFORE the load in the loop body, so
the dependency is only satisfiable across the back-edge. Two carry paths:

  * register-carried: ``buffer_load -> vgpr -> mfma/valu``. The consumer reads a
    register that is live-in at the top of the body (no in-body writer before it),
    so it binds to the body's LAST writer of that register -- the previous
    iteration's load.
  * LDS round-trip: ``buffer_load ... lds (band k) -> ds_read (band k)``. With
    ping-pong / multi-buffering the ds_read of band k reads what an EARLIER
    iteration's lds-load wrote; recognised via the resolved ``LdsModel`` bands.

This mirrors exactly what the waitcnt scoreboard binds across the back-edge
(``reorder/waitcnt.py`` loop fixpoint + the LDS band model), made explicit.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .model import Kind, Line


@dataclass
class PrefetchEdge:
    producer: int               # the prefetch load iid
    consumer: int               # the cross-iteration consumer iid (sits earlier)
    via: str                    # "reg" | "lds"
    reg: Optional[str] = None   # carried register (reg path)
    buffer: Optional[int] = None  # LDS band (lds path)
    distance: int = 0           # ~instructions of overlap across the back-edge
                                # = (body_len - pos(producer)) + pos(consumer)


@dataclass
class PrefetchInfo:
    edges: List[PrefetchEdge] = field(default_factory=list)
    producers: Set[int] = field(default_factory=set)   # prefetch load iids (guard set)
    consumers: Set[int] = field(default_factory=set)

    def consumer_of(self, producer: int) -> List[int]:
        return [e.consumer for e in self.edges if e.producer == producer]


def analyze_prefetch(order: List[int], line_of: Dict[int, Line], target,
                     lds_model=None) -> PrefetchInfo:
    """Recognise cross-iteration prefetch loads in one loop body (``order`` is the
    body's instruction iids in program order). ``lds_model`` (optional, resolved)
    enables the LDS-round-trip path. Pure read-only analysis."""
    info = PrefetchInfo()
    n = len(order)
    pos = {iid: i for i, iid in enumerate(order)}

    def _op(iid):
        return (line_of[iid].opcode or "").lower()

    # --- register-carried path --------------------------------------------
    writers: Dict[str, List[int]] = defaultdict(list)   # reg -> body positions
    readers: Dict[str, List[int]] = defaultdict(list)
    for iid in order:
        defs, uses = target.def_use(_op(iid), line_of[iid].operands)
        for r in defs:
            writers[r].append(pos[iid])
        for r in uses:
            readers[r].append(pos[iid])

    for iid in order:
        if target.classify(_op(iid), line_of[iid].operands) is not Kind.VMEM_LOAD:
            continue
        pL = pos[iid]
        defs, _ = target.def_use(_op(iid), line_of[iid].operands)
        for r in defs:
            wps = writers.get(r, [])
            if not wps or max(wps) != pL:
                continue                    # L is overwritten later -> not the binder
            for uPos in readers.get(r, []):
                # live-in consumer: no writer of r strictly before it in the body
                if not any(wp < uPos for wp in wps):
                    _add(info, iid, order[uPos], "reg", n, pL, uPos, reg=r)

    # --- LDS round-trip path ----------------------------------------------
    if lds_model is not None and getattr(lds_model, "resolved", False):
        band_loads: Dict[int, List[int]] = defaultdict(list)
        for iid in order:
            b = lds_model.write_buffer(iid)
            if b is not None:
                band_loads[b].append(pos[iid])
        for iid in order:
            if target.classify(_op(iid), line_of[iid].operands) is not Kind.DS_READ:
                continue
            b = lds_model.read_buffer(iid)
            if b is None:
                continue
            lps = band_loads.get(b, [])
            pR = pos[iid]
            if lps and not any(lp < pR for lp in lps):
                producer = order[max(lps)]
                _add(info, producer, iid, "lds", n, pos[producer], pR, buffer=b)

    return info


def _add(info: PrefetchInfo, producer: int, consumer: int, via: str, n: int,
         pProd: int, pCons: int, reg=None, buffer=None) -> None:
    info.edges.append(PrefetchEdge(producer, consumer, via, reg=reg,
                                   buffer=buffer, distance=(n - pProd) + pCons))
    info.producers.add(producer)
    info.consumers.add(consumer)
