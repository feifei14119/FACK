"""gfx942 dependency-edge construction (the ISA-specific half of the dep graph).

Edge rules added over an ordered list of instruction Nodes:

  RAW / WAR / WAW  register hazards over def/use unit sets (incl. implicit scc).
  MEM              conservative memory aliasing, per address space:
                     - VMEM (buffer/global/flat/scratch, incl. ``...lds`` reads)
                     - LDS  (ds_*, and the LDS-write side of ``buffer ...lds``)
                   loads may reorder past each other; any store orders with
                   every access on the same space.
  M0               s_add/s_mov m0 (LDS write offset) -> its ``buffer ...lds``
                   consumer(s) (RAW), and consumer -> next m0 writer (WAR),
                   m0 writer -> next m0 writer (WAW). This is the m0 Bundle.
  ACC              MFMA accumulation chain (consecutive MFMA writing the same
                   accumulator). MFMA writeback is scoreboard-tracked, so it is
                   NOT a memory counter -- ordering is via ACC/RAW edges only.
  FENCE            s_barrier / exec writers / branches / (conservatively)
                   existing s_waitcnt are marked as scheduling fences.

``m0`` is handled exclusively by the M0 rules (skipped in the generic register
pass) so its edges carry the M0 type rather than RAW/WAR/WAW.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from reorder.model import EdgeType, Kind
from . import classify as _cls


def _mem_effect(target, ln):
    """Return list of (space, role) for the line's memory side effects."""
    op = ln.opcode or ""
    hook = getattr(target, "mem_effects", None)
    if hook is not None:
        return hook(op.lower(), ln.operands)
    kind = target.classify(op, ln.operands)
    effects = []
    if target.is_lds_load(op, ln.operands):
        effects.append(("vmem", "load"))    # reads global
        effects.append(("lds", "store"))    # writes LDS
        return effects
    if kind is Kind.VMEM_LOAD:
        effects.append(("vmem", "load"))
    elif kind is Kind.VMEM_STORE:
        effects.append(("vmem", "store"))
    elif kind is Kind.DS_READ:
        effects.append(("lds", "load"))
    elif kind is Kind.DS_WRITE:
        effects.append(("lds", "store"))
    elif kind is Kind.SMEM:
        effects.append(("smem", "load"))    # s_load -> ordered conservatively
    return effects


def _is_matrix_op(target, op: str) -> bool:
    """Producer whose -> non-matrix RAW edges get the seed-calibrated distance."""
    hook = getattr(target, "calibrated_latency_producer", None)
    if hook is not None:
        return hook(op)
    return op.startswith("v_mfma") or op.startswith("v_smfmac")


def _reads_m0(target, op: str, operands) -> bool:
    hook = getattr(target, "reads_m0", None)
    return hook(op, operands) if hook is not None else _cls.reads_m0(op, operands)


def _is_extra_fence(target, op: str, operands) -> bool:
    """Arch-specific scheduling fences beyond barrier/wait/branch (gfx942: exec
    writers)."""
    hook = getattr(target, "is_sched_fence", None)
    return hook(op, operands) if hook is not None else _cls.writes_exec(op, operands)


def build_edges(target, nodes, graph) -> None:
    nbi = {n.iid: n for n in nodes}
    matrix_latency = getattr(target, "matrix_read_latency", _cls.mfma_read_latency)
    last_def: Dict[object, int] = {}
    readers: Dict[object, List[int]] = defaultdict(list)

    # memory state per space
    mem_last_store: Dict[str, int] = {}
    mem_loads: Dict[str, List[int]] = defaultdict(list)

    # m0 state
    m0_writer = None
    m0_readers: List[int] = []

    # MFMA accumulator chain
    last_mfma_def: Dict[object, int] = {}

    # MFMA-write -> non-MFMA-read RAW edges are deferred: their min-distance
    # (the MFMA result latency) is auto-calibrated below from the seed's own
    # tightest spacing per MFMA opcode.
    mfma_consumer_edges: List[tuple] = []

    for n in nodes:
        ln = n.line
        op = (ln.opcode or "").lower()
        kind = target.classify(op, ln.operands)

        # 'm0' is handled by the dedicated m0 rules below, not the register pass
        defs = {u for u in n.defs if u != "m0"}
        uses = {u for u in n.uses if u != "m0"}

        # --- register hazards ---------------------------------------------
        for u in uses:                         # RAW
            if u in last_def:
                a = last_def[u]
                # MFMA write -> NON-MFMA read carries the MFMA result latency
                # (back-to-back MFMA accumulation is pipelined -> stays dist 1).
                # Defer so the latency can be auto-calibrated from the seed.
                pop = ""
                if kind is not Kind.MFMA:
                    prod = nbi.get(a)
                    pop = (prod.line.opcode or "").lower() if prod else ""
                if pop and _is_matrix_op(target, pop):
                    mfma_consumer_edges.append((a, n.iid, pop))
                else:
                    graph.add_edge(a, n.iid, EdgeType.RAW)
        for d in defs:                         # WAW
            if d in last_def:
                graph.add_edge(last_def[d], n.iid, EdgeType.WAW)
        for d in defs:                         # WAR
            for r in readers.get(d, ()):
                graph.add_edge(r, n.iid, EdgeType.WAR)
        # commit register state
        for d in defs:
            last_def[d] = n.iid
            readers[d] = []
        for u in uses:
            readers[u].append(n.iid)

        # --- ACC chain (MFMA) ---------------------------------------------
        if kind is Kind.MFMA:
            for d in n.defs:
                if d in last_mfma_def:
                    graph.add_edge(last_mfma_def[d], n.iid, EdgeType.ACC)
            for d in n.defs:
                last_mfma_def[d] = n.iid

        # --- memory aliasing ----------------------------------------------
        for space, role in _mem_effect(target, ln):
            if role == "load":
                if space in mem_last_store:
                    graph.add_edge(mem_last_store[space], n.iid, EdgeType.MEM)
                mem_loads[space].append(n.iid)
            else:  # store
                if space in mem_last_store:
                    graph.add_edge(mem_last_store[space], n.iid, EdgeType.MEM)
                for r in mem_loads[space]:
                    graph.add_edge(r, n.iid, EdgeType.MEM)
                mem_last_store[space] = n.iid
                mem_loads[space] = []

        # --- m0 (RAW/WAR/WAW carrying the M0 type) ------------------------
        writes_m0 = "m0" in n.defs
        reads_m0 = _reads_m0(target, op, ln.operands)
        if reads_m0 and m0_writer is not None:
            graph.add_edge(m0_writer, n.iid, EdgeType.M0)       # RAW
            m0_readers.append(n.iid)
        if writes_m0:
            if m0_writer is not None:
                graph.add_edge(m0_writer, n.iid, EdgeType.M0)   # WAW
            for r in m0_readers:
                graph.add_edge(r, n.iid, EdgeType.M0)           # WAR
            m0_writer = n.iid
            m0_readers = []

        # --- fences -------------------------------------------------------
        if kind in (Kind.BARRIER, Kind.WAITCNT, Kind.BRANCH):
            graph.mark_fence(n.iid)
        elif _is_extra_fence(target, op, ln.operands):
            graph.mark_fence(n.iid)

    # --- MFMA result latency: auto-calibrate from the seed ----------------
    # The seed is known-correct, so the TIGHTEST MFMA-write -> non-MFMA-read
    # spacing it already uses (per MFMA opcode) is the empirically-safe latency.
    # Using the per-opcode minimum keeps the seed exactly legal while still
    # forbidding any reorder from hoisting a consumer closer. (Manually this is
    # how 16x16x32 == 3 was found.) classify.MFMA_READ_LATENCY is only a
    # fallback for an opcode whose consumer never appears in the seed.
    obs_min: Dict[str, int] = {}
    for a, b, pop in mfma_consumer_edges:
        gap = nbi[b].pos - nbi[a].pos
        if pop not in obs_min or gap < obs_min[pop]:
            obs_min[pop] = gap
    for a, b, pop in mfma_consumer_edges:
        dist = obs_min.get(pop) or matrix_latency(pop)
        graph.add_edge(a, b, EdgeType.RAW, dist=max(1, dist))


def bundles(target, nodes) -> List[List[int]]:
    """m0 Bundles: each m0 writer glued to the LDS-load consumer(s) that read it
    before the next m0 writer. Returned as lists of iids that must move together.
    """
    out: List[List[int]] = []
    current: List[int] = []
    for n in nodes:
        ln = n.line
        op = (ln.opcode or "").lower()
        if "m0" in n.defs:                 # new m0 writer
            if len(current) > 1:
                out.append(current)
            current = [n.iid]
        elif current and _reads_m0(target, op, ln.operands):
            current.append(n.iid)
        # a non-consumer between writer and consumer doesn't break the bundle
        # (the load just needs m0 intact until it issues); but a fence would.
    if len(current) > 1:
        out.append(current)
    return out
