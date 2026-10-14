"""Pure reorder engine (architecture-agnostic).

A ``RegionEditor`` reorders the instructions of one region, subject to the
``DepGraph`` legal windows and m0/bundle integrity. It is *pure*: it never
rewrites instruction text and never recomputes synchronization -- it only
changes instruction ORDER. Synchronization recompute (waitcnt) and forced nops
are the job of the M4 FixupPass pipeline; numerical/compile verification is the
final backstop.

Operations:
  - low level: ``move_before`` / ``move_after`` / ``swap`` (bundle-aware)
  - bundles:   ``lock_bundle`` (extra user-defined glued groups)
  - gap layout: ``set_gap_layout`` (per-gap heterogeneous filler placement)
  - cold start: ``distribute_evenly`` (spread a Kind across MFMA gaps)

Every mutation is validated against the legal window of the moved *unit* (a
single instruction, or a bundle moved as one contiguous block). Illegal moves
are rejected (``strict=True`` raises ``IllegalMove``; otherwise they are skipped
and recorded in the returned ``Diff.skipped``). Each op returns a reversible
``Diff``; ``revert`` restores the prior order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from . import regions
from .depgraph import DepGraph
from .model import EdgeType, Kind, Line, LineKind, Program
from .regions import Region, RegionKind


class IllegalMove(Exception):
    pass


class SkipReason(Enum):
    """Why a filler could not be placed into a requested MFMA gap. Reported by
    ``RegionEditor.propose_layouts`` so the caller (AI/search) can adjust its
    next per-slot layout intent."""

    SLOT_OOR = "slot_out_of_range"      # slot index >= number of anchors
    WINDOW_EMPTY = "window_empty"       # legal window collapsed (lo > hi)
    FENCE_BLOCKED = "fence_blocked"     # a fence sits between current pos and target gap
    MFMA_LATENCY = "mfma_latency"       # violates an MFMA write->read min-distance edge
    LDS_ROUNDTRIP = "lds_roundtrip"     # ds_read must wait on the buffer..lds filling its band
    RAW = "raw"
    WAR = "war"
    WAW = "waw"
    MEM = "mem"                         # conservative memory-alias ordering
    M0_BUNDLE = "m0_bundle"             # m0-bundle integrity
    ACC = "acc_chain"                   # MFMA accumulation chain
    PREFETCH_PROTECTED = "prefetch_protected"   # recognised prefetch load: hoist-only
                                                # (sinking would shrink cross-iter overlap)


_ETYPE_TO_REASON = {
    EdgeType.RAW: SkipReason.RAW,
    EdgeType.WAR: SkipReason.WAR,
    EdgeType.WAW: SkipReason.WAW,
    EdgeType.MEM: SkipReason.MEM,
    EdgeType.M0: SkipReason.M0_BUNDLE,
    EdgeType.ACC: SkipReason.ACC,
    EdgeType.FENCE: SkipReason.FENCE_BLOCKED,
}

# when several edge types bind the same pair, report the most specific one
_EDGE_PRIORITY = [EdgeType.M0, EdgeType.ACC, EdgeType.WAW, EdgeType.WAR,
                  EdgeType.RAW, EdgeType.MEM, EdgeType.FENCE]


@dataclass
class Placement:
    """Result of placing one filler into one slot (gap after ``anchors[slot]``)."""

    iid: int
    slot: int
    ok: bool
    reason: Optional[SkipReason] = None   # set iff ok is False
    window: Tuple[int, int] = (-1, -1)    # legal position window [lo, hi]
    bound_iid: Optional[int] = None       # the instruction (pred/succ/fence) that blocked it


@dataclass
class LayoutReport:
    """Outcome of one candidate ``{slot: [filler...]}`` layout (non-committing)."""

    layout: Dict[int, List[int]]
    placed: List[Placement] = field(default_factory=list)
    skipped: List[Placement] = field(default_factory=list)
    legal: bool = False

    @property
    def all_placed(self) -> bool:
        return not self.skipped


@dataclass
class OrderReport:
    """Outcome of one (partial/full) linear-order intent for an ANCHOR-LESS region
    (non-committing). The agent lists iids in the order it wants; the engine
    realises that relative order where legal and reports the rest with reasons.
    This is the prologue/epilogue counterpart of LayoutReport (M9 Phase 3)."""

    order_intent: List[int]
    placed: List["Placement"] = field(default_factory=list)
    skipped: List["Placement"] = field(default_factory=list)
    legal: bool = False
    cost: Optional[Dict] = None        # RegionCost.to_dict() of the realised order
    error: Optional[str] = None        # set (with legal=False) when the intent is
                                       # rejected without evaluation (e.g. too long)


@dataclass
class Diff:
    """Reversible record of an editor operation (an instruction-order change)."""

    op: str
    old_order: List[int]
    new_order: List[int]
    note: str = ""
    skipped: List[int] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.old_order != self.new_order


class RegionEditor:
    def __init__(self, program: Program, target, region: Region,
                 treat_waitcnt_as_fence: bool = True,
                 protect_prefetch: bool = False) -> None:
        """``treat_waitcnt_as_fence``: when True (default, safe) existing
        ``s_waitcnt`` block movement. Set False for cold-start scheduling where
        synchronization will be recomputed afterwards by the M4 pipeline -- then
        instructions may freely cross existing waitcnt.

        ``protect_prefetch``: when True, loads recognised as cross-iteration
        prefetch (``reorder.prefetch``) become *hoist-only* -- reorder may move
        them EARLIER (more overlap) but never LATER, so a reschedule cannot
        scatter the design-time prefetch schedule and lose its memory/compute
        overlap. Pure performance guard; correctness is unaffected."""
        self.program = program
        self.target = target
        self.region = region
        self.instr_lines: List[Line] = regions.region_instr_lines(program, region)
        # original program-list positions of the region's instruction lines.
        # On a freshly parsed program, Line.idx == its index in program.lines.
        self._slots: List[int] = [ln.idx for ln in self.instr_lines]
        self._line_of: Dict[int, Line] = {ln.idx: ln for ln in self.instr_lines}
        self.graph = DepGraph.build(self.instr_lines, target)
        joins = set(self._join_fences())
        self.graph.add_fences(joins)
        self.order: List[int] = [ln.idx for ln in self.instr_lines]
        self._fences = self.graph.fences()
        if not treat_waitcnt_as_fence:
            self._fences = {i for i in self._fences
                            if i in joins or self.kind_of(i) is not Kind.WAITCNT}
        # bundles: iid -> the contiguous group it must move with
        self._bundle_of: Dict[int, List[int]] = {}
        for b in target.bundles(self.graph.nodes):
            for i in b:
                self._bundle_of[i] = b
        # prefetch guard: loads whose data is consumed in a LATER iteration are
        # recognised once on the as-designed order and pinned to hoist-only.
        self._protect_prefetch = protect_prefetch
        self._prefetch = self._build_prefetch() if protect_prefetch else None
        self._prefetch_loads = set(self._prefetch.producers) if self._prefetch else set()

    def _join_fences(self) -> List[int]:
        """First instruction after every label inside the region: a label is a
        possible branch target, and moving code across it changes which paths
        execute that code (e.g. sinking a conditionally skipped store past its
        join makes it unconditional)."""
        if not self.instr_lines:
            return []
        first = self.instr_lines[0].idx
        out: List[int] = []
        pending = False
        for ln in self.program.lines:
            if ln.idx <= first or ln.idx > self.region.line_end:
                continue
            if ln.kind is LineKind.LABEL:
                pending = True
            elif ln.kind is LineKind.INSTR and pending:
                out.append(ln.idx)
                pending = False
        return out

    def _build_prefetch(self):
        from . import prefetch as _pf
        lds = None
        if hasattr(self.target, "lds_roundtrip_model"):
            text = [it.line for it in regions._collect_code_items(self.program)
                    if it.line.kind is LineKind.INSTR]
            lds = self.target.lds_roundtrip_model(text, scope_idxs=set(self.order))
        return _pf.analyze_prefetch(self.order, self._line_of, self.target,
                                    lds_model=lds)

    def prefetch_info(self):
        """Read-only cross-iteration prefetch recognition for this region
        (built on demand even when the guard is off)."""
        if self._prefetch is None:
            self._prefetch = self._build_prefetch()
        return self._prefetch

    # --- position index (O(1) lookups; rebuilt only when order changes) ----
    def _pos(self) -> Dict[int, int]:
        """``iid -> current index`` map, cached against the CURRENT order object.

        Every mutation reassigns ``self.order`` to a NEW list (never mutates in
        place), so an identity (``is``) check on the held reference is a reliable,
        cheap cache guard -- and holding that reference prevents id reuse. This
        replaces the O(n) ``self.order.index(...)`` scans in the hot move / order
        paths, so ``propose_orders`` no longer pays O(n) per lookup (large-DAG
        anchor-less regions; proj/brainstorm/anchorless_fullorder_propose_perf.md
        direction B)."""
        if getattr(self, "_pos_cache_order", None) is not self.order:
            self._pos_cache_order = self.order
            self._pos_cache = {x: i for i, x in enumerate(self.order)}
        return self._pos_cache

    # --- introspection -----------------------------------------------------
    def kind_of(self, iid: int) -> Kind:
        ln = self._line_of[iid]
        return self.target.classify(ln.opcode or "", ln.operands)

    def opcode_of(self, iid: int) -> str:
        """Raw mnemonic of an instruction (e.g. ``v_mfma_f32_32x32x8_bf16``,
        ``ds_read_b128``). Lets callers sub-type within a coarse ``Kind`` --
        different MFMA shapes / LDS widths have different latency + capacity."""
        return self._line_of[iid].opcode or ""

    def anchors(self, kind: Kind = Kind.MFMA) -> List[int]:
        """iids of the given kind in current order (default MFMA = gap anchors)."""
        return [i for i in self.order if self.kind_of(i) is kind]

    def unit(self, iid: int) -> List[int]:
        """The block that must move together with ``iid`` (its bundle, or itself),
        returned in current order."""
        members = set(self._bundle_of.get(iid, [iid]))
        return [x for x in self.order if x in members]

    # --- legality ----------------------------------------------------------
    def _block_insert_range(self, members: Sequence[int]):
        """Inclusive ``(lo, hi)`` insertion-index range (in the order WITHOUT the
        block) at which the contiguous block may be reinserted."""
        member_set = set(members)
        order_wo = [x for x in self.order if x not in member_set]
        idx = {x: i for i, x in enumerate(order_wo)}
        lo, hi = 0, len(order_wo)

        posmap = self._pos()
        positions = [posmap[m] for m in members]
        cur_lo, cur_hi = min(positions), max(positions)

        # stay within the current fence-bounded segment
        left = right = None
        for f in self._fences:
            fp = posmap[f]
            if fp < cur_lo:
                left = fp if left is None else max(left, fp)
            elif fp > cur_hi:
                right = fp if right is None else min(right, fp)
        if left is not None:
            lo = max(lo, idx[self.order[left]] + 1)
        if right is not None:
            hi = min(hi, idx[self.order[right]])

        # dependency neighbours outside the block (honour per-edge latency: a
        # plain edge needs dist 1; an MFMA-write -> non-MFMA-read edge needs the
        # MFMA result latency, so the consumer can't be inserted too close).
        for m in members:
            for p in self.graph.preds(m):
                if p in idx:
                    lo = max(lo, idx[p] + self.graph.dist(p, m))
            for s in self.graph.succs(m):
                if s in idx:
                    hi = min(hi, idx[s] + 1 - self.graph.dist(m, s))
        if self._protect_prefetch and (member_set & self._prefetch_loads):
            hi = min(hi, cur_lo)            # hoist-only: never sink a prefetch load
        return lo, hi, order_wo

    def _apply_block(self, members: List[int], k: int, order_wo: List[int]) -> None:
        self.order = order_wo[:k] + members + order_wo[k:]

    def _move_unit_to(self, iid: int, k_anchor_iid: Optional[int], after: bool,
                      op: str, strict: bool) -> Diff:
        if iid in self._fences:
            if strict:
                raise IllegalMove("cannot move fence instruction {}".format(iid))
            return Diff(op, list(self.order), list(self.order), "fence not movable",
                        skipped=[iid])
        members = self.unit(iid)
        if k_anchor_iid is not None and k_anchor_iid in set(members):
            if strict:
                raise IllegalMove("anchor {} is inside the moved unit".format(k_anchor_iid))
            return Diff(op, list(self.order), list(self.order),
                        "anchor inside unit", skipped=[iid])
        lo, hi, order_wo = self._block_insert_range(members)
        # desired insertion index from the anchor (anchor is in order_wo)
        widx = {x: i for i, x in enumerate(order_wo)}
        if k_anchor_iid is None:
            k = max(lo, min(hi, 0))
        else:
            base = widx[k_anchor_iid]
            k = base + 1 if after else base
        old = list(self.order)
        if lo <= k <= hi:
            self._apply_block(members, k, order_wo)
            return Diff(op, old, list(self.order))
        if strict:
            raise IllegalMove(
                "move of {} to index {} outside legal window [{},{}]".format(
                    iid, k, lo, hi))
        return Diff(op, old, old, "illegal: window [{},{}]".format(lo, hi),
                    skipped=list(members))

    # --- low-level primitives ---------------------------------------------
    def move_after(self, iid: int, anchor_iid: int, strict: bool = True) -> Diff:
        return self._move_unit_to(iid, anchor_iid, True, "move_after", strict)

    def move_before(self, iid: int, anchor_iid: int, strict: bool = True) -> Diff:
        return self._move_unit_to(iid, anchor_iid, False, "move_before", strict)

    def swap(self, iid_a: int, iid_b: int, strict: bool = True) -> Diff:
        """Swap two instructions if both relocations are legal."""
        old = list(self.order)
        posmap = self._pos()
        pa, pb = posmap[iid_a], posmap[iid_b]
        first, second = (iid_a, iid_b) if pa < pb else (iid_b, iid_a)
        # move the earlier one to just after the later one, then the later one
        # to where the earlier one was -- validate via legal windows.
        d1 = self.move_after(first, second, strict=False)
        if not d1.changed:
            if strict:
                raise IllegalMove("swap({},{}) illegal".format(iid_a, iid_b))
            return Diff("swap", old, old, "illegal", skipped=[iid_a, iid_b])
        d2 = self.move_before(second, first, strict=False)
        if not self.graph.is_order_legal(self.order, fences=self._fences):
            self.order = old
            if strict:
                raise IllegalMove("swap({},{}) illegal".format(iid_a, iid_b))
            return Diff("swap", old, old, "illegal", skipped=[iid_a, iid_b])
        return Diff("swap", old, list(self.order))

    def lock_bundle(self, iids: Sequence[int]) -> None:
        """Glue an extra user-defined group so it moves as one contiguous unit."""
        group = [x for x in self.order if x in set(iids)]
        for i in group:
            self._bundle_of[i] = group

    # --- per-instruction scheduling (L2: on top of an already-scheduled seed) -
    def _place_unit_extreme(self, iid: int, earliest: bool,
                            bound: Optional[int] = None) -> bool:
        """Move ``iid``'s unit to the earliest (or latest) position its legal
        window allows, optionally clamped by ``bound`` (a barrier iid in the
        order-without-block whose position the unit must stay after, when
        hoisting, or before, when sinking) to preserve relative order among the
        same-kind units. Returns True if the order changed."""
        if iid in self._fences:
            return False
        members = self.unit(iid)
        lo, hi, order_wo = self._block_insert_range(members)
        if lo > hi:
            return False
        if bound is not None and bound in order_wo:
            bpos = order_wo.index(bound)
            if earliest:
                lo = max(lo, bpos + 1)        # stay AFTER the previous unit
            else:
                hi = min(hi, bpos)            # stay BEFORE the previous unit
            if lo > hi:
                return False
        k = lo if earliest else hi
        before = list(self.order)
        self._apply_block(members, k, order_wo)
        return self.order != before

    def _enforce_min_distance(self) -> bool:
        """Repair latency (min-distance > 1) violations that a multi-unit pass
        can introduce: hoisting a gap-filler out of a ``[MFMA, consumer]`` gap
        shrinks an absolute distance another unit already relied on. Repeatedly
        re-seat the *topmost* violating consumer at its current legal earliest
        position (which encodes ``pred.pos + latency``) -- a strictly-downward
        move, so this terminates. Returns False if a consumer is boxed in by its
        own successors (infeasible at this aggressiveness)."""
        g = self.graph
        lat = g.latency_edges()
        if not lat:
            return True
        budget = len(self.order) + 1
        for _ in range(budget):
            pos = {iid: i for i, iid in enumerate(self.order)}
            worst = None
            for a, b, d in lat:
                if pos[b] - pos[a] < d:
                    if worst is None or pos[b] < pos[worst]:
                        worst = b
            if worst is None:
                return True
            if not self._place_unit_extreme(worst, earliest=True):
                return False          # boxed in by its own successors
        return False

    def compact_kind(self, kind: Kind, earliest: bool = True) -> Diff:
        """Slide every unit of ``kind`` to its legal-window extreme in a stable
        pass that PRESERVES the units' relative order. ``earliest=True`` hoists
        (e.g. issue async loads as early as legal -> longer load->use distance,
        more compute/memory overlap); ``earliest=False`` sinks.

        This is the L2 per-instruction reorder: it runs ON TOP of an already-
        scheduled seed (the current kernel) and only tightens placement; it does
        NOT redistribute. Correctness is preserved (legal windows already encode
        all fence + dependency constraints); the following waitcnt recompute then
        re-derives the minimal waits for the new schedule."""
        old = list(self.order)
        # hoist: settle from the top so each unit clamps after the previous one;
        # sink: settle from the bottom (reversed) clamping before the previous.
        units = [i for i in self.order if self.kind_of(i) is kind]
        if not earliest:
            units = list(reversed(units))
        moved = 0
        prev = None
        for iid in units:
            if self._place_unit_extreme(iid, earliest, bound=prev):
                moved += 1
            prev = iid
        if not self._enforce_min_distance():
            self.order = old
            return Diff("compact_kind", old, old,
                        "kind={} reverted: min-distance infeasible".format(kind.value))
        note = "kind={} earliest={} moved={}".format(kind.value, earliest, moved)
        if self.order != old and moved == 0:
            note += " (distance-repair only)"
        return Diff("compact_kind", old, list(self.order), note)

    # --- high-level: per-gap layout ---------------------------------------
    def set_gap_layout(self, anchors: Sequence[int], layout: Dict[int, List[int]],
                       strict: bool = False) -> Diff:
        """Place fillers into MFMA gaps. ``anchors`` is an ordered anchor list;
        ``layout[g]`` lists the filler iids to place in the gap *after*
        ``anchors[g]`` (before ``anchors[g+1]``), in the given order."""
        old = list(self.order)
        skipped: List[int] = []
        for g in sorted(layout):
            if g >= len(anchors):
                continue
            prev = anchors[g]
            for f in layout[g]:
                d = self.move_after(f, prev, strict=False)
                if d.changed:
                    prev = f
                elif strict:
                    raise IllegalMove("filler {} illegal in gap {}".format(f, g))
                else:
                    skipped.extend(d.skipped)
        return Diff("set_gap_layout", old, list(self.order),
                    "{} gaps".format(len(layout)), skipped=skipped)

    # --- diagnostics for AI-directed per-slot layouts (M6a) ----------------
    def _window_with_cause(self, members: Sequence[int]):
        """Like ``_block_insert_range`` but also tracks which iid binds ``lo``
        and ``hi`` (and the reason). Returns ``(lo, hi, idx, lo_cause, hi_cause)``
        where ``idx`` maps iid -> position in the order WITHOUT the block, and a
        cause is ``(bound_iid, SkipReason)`` or ``None``."""
        member_set = set(members)
        order_wo = [x for x in self.order if x not in member_set]
        idx = {x: i for i, x in enumerate(order_wo)}
        lo, hi = 0, len(order_wo)
        lo_cause = hi_cause = None

        posmap = self._pos()
        positions = [posmap[m] for m in members]
        cur_lo, cur_hi = min(positions), max(positions)

        left = right = None
        left_f = right_f = None
        for f in self._fences:
            fp = posmap[f]
            if fp < cur_lo and (left is None or fp > left):
                left, left_f = fp, f
            elif fp > cur_hi and (right is None or fp < right):
                right, right_f = fp, f
        if left is not None:
            cand = idx[self.order[left]] + 1
            if cand > lo:
                lo, lo_cause = cand, (left_f, SkipReason.FENCE_BLOCKED)
        if right is not None:
            cand = idx[self.order[right]]
            if cand < hi:
                hi, hi_cause = cand, (right_f, SkipReason.FENCE_BLOCKED)

        for m in members:
            for p in self.graph.preds(m):
                if p in idx:
                    d = self.graph.dist(p, m)
                    cand = idx[p] + d
                    if cand > lo:
                        lo, lo_cause = cand, (p, self._edge_reason(p, m, d))
            for s in self.graph.succs(m):
                if s in idx:
                    d = self.graph.dist(m, s)
                    cand = idx[s] + 1 - d
                    if cand < hi:
                        hi, hi_cause = cand, (s, self._edge_reason(m, s, d))
        if self._protect_prefetch and (member_set & self._prefetch_loads) and cur_lo < hi:
            cons = next((c for m in members for c in self._prefetch.consumer_of(m)),
                        None)
            hi, hi_cause = cur_lo, (cons, SkipReason.PREFETCH_PROTECTED)
        return lo, hi, idx, lo_cause, hi_cause

    def _edge_reason(self, a: int, b: int, dist: int) -> SkipReason:
        """Classify the a->b ordering constraint into a SkipReason."""
        if dist > 1:
            return SkipReason.MFMA_LATENCY
        # LDS round-trip: a buffer..lds load feeding a ds_read of the same band
        if self.kind_of(b) is Kind.DS_READ and self.kind_of(a) is Kind.VMEM_LOAD:
            return SkipReason.LDS_ROUNDTRIP
        types = self.graph.edge_types(a, b)
        for et in _EDGE_PRIORITY:
            if et in types:
                return _ETYPE_TO_REASON[et]
        return SkipReason.RAW

    def _diagnose_skip(self, f: int, anchor: int) -> Placement:
        """Explain why ``move_after(f, anchor)`` would be rejected, as a failed
        ``Placement`` (reason + window + the blocking iid)."""
        if f in self._fences:
            return Placement(f, -1, False, SkipReason.FENCE_BLOCKED, (-1, -1), f)
        lo, hi, idx, lo_c, hi_c = self._window_with_cause(self.unit(f))
        if lo > hi:
            cause = lo_c or hi_c
            return Placement(f, -1, False, SkipReason.WINDOW_EMPTY, (lo, hi),
                             cause[0] if cause else None)
        k = (idx[anchor] + 1) if anchor in idx else None
        cause = None
        if k is None or k < lo:
            cause = lo_c
        elif k > hi:
            cause = hi_c
        if cause is None:
            cause = lo_c or hi_c
        if cause is None:
            return Placement(f, -1, False, SkipReason.WINDOW_EMPTY, (lo, hi), None)
        return Placement(f, -1, False, cause[1], (lo, hi), cause[0])

    def propose_layouts(self, anchors: Sequence[int],
                        candidates: Sequence[Dict[int, List[int]]],
                        strict: bool = False) -> List[LayoutReport]:
        """Validate a batch of AI-proposed per-slot layouts WITHOUT committing.

        Each candidate is a ``{slot: [filler_iid, ...]}`` intent: place those
        fillers into the gap after ``anchors[slot]`` (in the given order). For
        every candidate the editor tries the placement on a clean copy of the
        current order, records which fillers landed (``placed``) and which were
        rejected with a ``SkipReason`` (``skipped``), then reverts -- so the
        editor's order is left UNCHANGED. The caller picks a layout and applies
        it explicitly via :meth:`set_gap_layout`.

        ``strict=True`` raises ``IllegalMove`` on the first rejected filler."""
        base = list(self.order)
        reports: List[LayoutReport] = []
        try:
            for layout in candidates:
                self.order = list(base)
                placed: List[Placement] = []
                skipped: List[Placement] = []
                for g in sorted(layout):
                    if g >= len(anchors):
                        for f in layout[g]:
                            if strict:
                                raise IllegalMove(
                                    "slot {} >= anchor count {}".format(g, len(anchors)))
                            skipped.append(Placement(f, g, False, SkipReason.SLOT_OOR))
                        continue
                    prev = anchors[g]
                    for f in layout[g]:
                        win = self._window_with_cause(self.unit(f))[:2]
                        d = self.move_after(f, prev, strict=False)
                        if d.changed:
                            placed.append(Placement(f, g, True, None, win, None))
                            prev = f
                        else:
                            p = self._diagnose_skip(f, prev)
                            p.slot = g
                            if strict:
                                raise IllegalMove(
                                    "filler {} illegal in slot {} ({})".format(
                                        f, g, p.reason.value if p.reason else "?"))
                            skipped.append(p)
                reports.append(LayoutReport(dict(layout), placed, skipped, self.is_legal()))
        finally:
            self.order = base
        return reports

    # --- anchor-less linear-order intents (M9 Phase 3) ---------------------
    def _materialized_region_cost(self) -> Optional[Dict]:
        """Best-effort RegionCost of the CURRENT order (pre-recompute proxy):
        temporarily materialize the order, estimate, then restore the lines.
        Waits are not recomputed here, so this is a relative ordering signal
        (the committed est_cycles in AgentSession reflects the recomputed waits)."""
        from . import cost as _cost
        snapshot = {slot: self.program.lines[slot] for slot in self._slots}
        try:
            self.materialize()
            return _cost.estimate(self.program, self.target, self.region).to_dict()
        except Exception:
            return None
        finally:
            for slot, ln in snapshot.items():
                self.program.lines[slot] = ln

    def propose_orders(self, candidates: Sequence[Sequence[int]],
                       strict: bool = False,
                       max_intent: Optional[int] = None) -> List[OrderReport]:
        """Validate a batch of AI-proposed linear-order intents WITHOUT committing.

        Each candidate is a (partial or full) list of iids in the order the agent
        wants them to appear. The editor realises that RELATIVE order greedily on
        a clean copy of the current order: each listed iid is moved to just after
        the previously-placed one (via the legal-window machinery). iids that
        cannot reach the requested relative position are reported as ``skipped``
        with a ``SkipReason`` + window + blocking iid; unlisted instructions keep
        their relative order and fill around. The editor's order is left
        UNCHANGED (try/revert). ``strict=True`` raises on the first rejected iid.

        ``max_intent`` (when set) is a soft guardrail: a candidate whose intent
        lists more than ``max_intent`` iids is REJECTED in O(1) with an ``error``
        (legal=False), never evaluated. This stops the anchor-less O(n^2)
        full-order collapse (a 426-iid order used to hang propose for >8 min);
        the agent should list only the few iids it wants to move (a PARTIAL
        order) and let the rest fill around them."""
        base = list(self.order)
        reports: List[OrderReport] = []
        try:
            for intent in candidates:
                if max_intent is not None and len(intent) > max_intent:
                    if strict:
                        raise IllegalMove(
                            "order intent too long: {} > limit {}".format(
                                len(intent), max_intent))
                    reports.append(OrderReport(
                        list(intent), legal=False,
                        error=("order too long: {} iids > limit {}; list only the "
                               "few iids you want to move (partial order) and let "
                               "the rest fill around them".format(
                                   len(intent), max_intent))))
                    continue
                self.order = list(base)
                placed: List[Placement] = []
                skipped: List[Placement] = []
                prev: Optional[int] = None
                for f in intent:
                    if f not in self._line_of:
                        if strict:
                            raise IllegalMove("iid {} not in region".format(f))
                        skipped.append(Placement(f, -1, False, SkipReason.SLOT_OOR))
                        continue
                    win = self._window_with_cause(self.unit(f))[:2]
                    if prev is None:
                        placed.append(Placement(f, -1, True, None, win, None))
                        prev = f
                        continue
                    d = self.move_after(f, prev, strict=False)
                    posmap = self._pos()
                    after_prev = posmap[f] > posmap[prev]
                    if d.changed or after_prev:
                        placed.append(Placement(f, -1, True, None, win, None))
                        prev = f
                    else:
                        p = self._diagnose_skip(f, prev)
                        if strict:
                            raise IllegalMove("iid {} illegal after {} ({})".format(
                                f, prev, p.reason.value if p.reason else "?"))
                        skipped.append(p)
                legal = self.is_legal()
                cost = self._materialized_region_cost() if legal else None
                reports.append(OrderReport(list(intent), placed, skipped, legal, cost))
        finally:
            self.order = base
        return reports

    def distribute_evenly(self, kind: Kind, anchor_lo: int, anchor_hi: int,
                          fillers: Optional[List[int]] = None,
                          strict: bool = False) -> Diff:
        """Spread instructions of ``kind`` evenly across the gaps between MFMA
        anchors ``anchor_lo..anchor_hi`` (inclusive).

        Use this ONLY to bootstrap a **completely unoptimized** kernel -- one
        just written for correctness, ops still clustered by type (all MFMA
        together, all buffer_load together, all ds_read/write together) -- into a
        usable seed by spreading the memory ops into the MFMA stream. It is NOT
        an optimization level, and NOT needed for an already-optimized kernel:
        there the kernel itself IS the seed (and the performance baseline), so
        you run the opt-level ladder (see reorder.optlevel) directly on it and do
        NOT re-distribute (doing so just scrambles the existing schedule)."""
        old = list(self.order)
        mfma = self.anchors(Kind.MFMA)
        if not (0 <= anchor_lo <= anchor_hi < len(mfma)):
            raise IllegalMove("anchor range [{},{}] out of MFMA count {}".format(
                anchor_lo, anchor_hi, len(mfma)))
        span = mfma[anchor_lo:anchor_hi + 1]
        ngaps = len(span) - 1
        if ngaps < 1:
            return Diff("distribute_evenly", old, old, "no gaps in anchor span")
        if fillers is None:
            fillers = [i for i in self.order if self.kind_of(i) is kind]
        if not fillers:
            return Diff("distribute_evenly", old, old, "no fillers of kind")

        layout: Dict[int, List[int]] = {}
        per, rem = divmod(len(fillers), ngaps)
        i = 0
        for g in range(ngaps):
            cnt = per + (1 if g < rem else 0)
            if cnt:
                layout[g] = fillers[i:i + cnt]
                i += cnt
        d = self.set_gap_layout(span, layout, strict=strict)
        return Diff("distribute_evenly", old, list(self.order),
                    "kind={} gaps={} fillers={}".format(kind.value, ngaps, len(fillers)),
                    skipped=d.skipped)

    # --- commit / rollback -------------------------------------------------
    def revert(self, diff: Diff) -> None:
        self.order = list(diff.old_order)

    def is_legal(self) -> bool:
        return self.graph.is_order_legal(self.order, fences=self._fences)

    def materialize(self) -> Program:
        """Write the current instruction order back into the program (in place),
        keeping every non-instruction line at its original position. Returns the
        program for convenience."""
        for slot, iid in zip(self._slots, self.order):
            self.program.lines[slot] = self._line_of[iid]
        return self.program


def span_editor(program: Program, target, region_list: Sequence[Region],
                treat_waitcnt_as_fence: bool = False) -> "RegionEditor":
    """Build a ``RegionEditor`` over the contiguous span covering ``region_list``,
    enabling SAFE cross-region moves between regions of the SAME execution count
    (e.g. prologue <-> inter <-> epilogue, or a single-iteration tail).

    Every LOOP region inside the span is SEALED: its first and last instructions
    are pinned as fences, so no unit can be hoisted/sunk into or out of a loop
    body. That boundary is not a mere ordering constraint -- crossing it changes
    how many times the instruction runs. Sinking e.g. a prologue prefetch INTO
    the loop body is a software-pipelining transform (it needs a compensating
    copy for iteration 0 / a rotated steady state) and is therefore NOT
    expressible as a pure-order move; it stays out of scope of this editor.

    Within the span, ordinary legal-window + fence rules apply, so a unit can
    move across a (non-loop) region boundary only when no fence and no
    dependency forbids it -- exactly the safe set of cross-region relocations.
    """
    regs = sorted(region_list, key=lambda r: r.line_start)
    if not regs:
        raise ValueError("span_editor needs at least one region")
    span = Region(kind=regs[0].kind, line_start=regs[0].line_start,
                  line_end=regs[-1].line_end)
    ed = RegionEditor(program, target, span, treat_waitcnt_as_fence)
    for r in regs:
        if r.kind is RegionKind.LOOP:
            body = [ln.idx for ln in ed.instr_lines
                    if r.line_start <= ln.idx <= r.line_end]
            if body:
                ed._fences.add(body[0])
                ed._fences.add(body[-1])
    return ed
