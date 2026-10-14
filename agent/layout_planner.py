"""Layer 3 constraint consumer: turn the gold-mined fine-grained QUANT skills
(``per_slot_capacity`` / ``adjacent_cooccur`` / ``mfma_gap_size`` /
``intra_gap_order`` + ``conflict_groups``) into a small ranked set of CANDIDATE
MFMA-gap layouts for a fresh, un-scheduled kernel.

Design contract (same red line as the rest of the meta layer):

  * This only NAVIGATES -- it proposes WHERE to place each movable filler
    (a ``{slot: [iid, ...]}`` intent that ``RegionEditor.propose_layouts`` / 
    ``AgentSession.propose`` understands). Legality is still gated by the engine
    on propose; performance is still decided by hardware on commit.
  * It NEVER invents numbers: every capacity / stride / ordering decision is
    derived from the MEASURED constraint stats handed in via ``prior_plan``.
  * ``conflict_groups`` (e.g. "pack many ds_read per slot" vs "don't fill
    adjacent slots with ds_read") are not adjudicated here: each conflicting
    kind yields TWO policy variants (pack vs spread) and we emit the cartesian
    product as separate candidates, each SCORED by the summed ``weight`` (times
    a confidence multiplier) of the constraints it satisfies. The agent / search
    then HW-evaluates the top-K and lets the real measurement pick the winner.

The planner is a PURE function of plain data, so it is fully unit-testable
without a GPU, an editor, or a parsed kernel.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

# Canonical MFMA-shape parser, shared with the miner (tools/mine_corpus.py imports
# it). A gap's capacity depends on the SHAPE of the MFMA that opens it (different
# result latency => different-sized gap), so both the miner (keying measured stats)
# and the planner (sizing per-gap placement) must agree on the class token.
_MFMA_SHAPE_RE = re.compile(r"\d+x\d+x\d+")


def mfma_shape_class(opcode: Optional[str]) -> str:
    """MFMA shape token (``16x16x16``, ``32x32x8`` ...); ``"mfma"`` when the
    mnemonic carries no MxNxK shape (never dropped)."""
    if not opcode:
        return "mfma"
    m = _MFMA_SHAPE_RE.search(opcode)
    return m.group(0) if m else "mfma"


# ---------------------------------------------------------------------------
# Constraint lookups (read the measured stats out of a prior_plan constraint list)
# ---------------------------------------------------------------------------
def _capacity(constraints: List[Dict], kind: str,
              mfma_class: Optional[str] = None) -> Optional[Dict]:
    """Kind-level per-slot capacity. When ``mfma_class`` is given, prefer the
    constraint measured for THAT MFMA shape and fall back to the pooled one.
    Width sub-constraints (they carry ``width``) are for reporting, not placement."""
    pooled = None
    for c in constraints:
        if c.get("metric") != "per_slot_capacity" or c.get("kind") != kind:
            continue
        if c.get("width"):
            continue
        cls = c.get("mfma_class")
        if mfma_class is not None and cls == mfma_class:
            return c
        if cls is None and pooled is None:
            pooled = c
    return pooled


def _cooccur(constraints: List[Dict], kind: str) -> Optional[Dict]:
    for c in constraints:
        if (c.get("metric") == "adjacent_cooccur" and c.get("kind") == kind
                and not c.get("mfma_class")):
            return c
    return None


def _gap_size(constraints: List[Dict],
              mfma_class: Optional[str] = None) -> Optional[Dict]:
    pooled = None
    for c in constraints:
        if c.get("metric") != "mfma_gap_size":
            continue
        cls = c.get("mfma_class")
        if mfma_class is not None and cls == mfma_class:
            return c
        if cls is None and pooled is None:
            pooled = c
    return pooled


def _order_rank(constraints: List[Dict]) -> Dict[str, int]:
    """Map kind -> rank from intra_gap_order precedences (lower = earlier in a
    gap). Rank = number of kinds that must precede it (in-degree); ties keep a
    stable, arbitrary-but-deterministic order."""
    indeg: Counter = Counter()
    kinds = set()
    for c in constraints:
        if c.get("metric") == "intra_gap_order":
            a, b = c.get("before"), c.get("after")
            kinds.update((a, b))
            indeg[b] += 1
    return {k: indeg.get(k, 0) for k in kinds}


# ---------------------------------------------------------------------------
# Placement primitives
# ---------------------------------------------------------------------------
def _slot_priority(n_slots: int, stride: int) -> List[int]:
    """Order in which slots get filled. stride<=1 => every slot left-to-right;
    stride>=2 => strided slots FIRST (so an "avoid adjacency" kind lands in
    non-neighbouring slots), then the skipped ones only if we run out."""
    if stride <= 1:
        return list(range(n_slots))
    primary = list(range(0, n_slots, stride))
    rest = [s for s in range(n_slots) if s % stride != 0]
    return primary + rest


def _distribute(iids: List[int], n_slots: int, cap: int,
                stride: int) -> Dict[int, List[int]]:
    """Spread ``iids`` of one kind across slots: ``cap`` per chosen slot, walking
    ``_slot_priority``; wrap (slots may receive a 2nd group) only if there are
    more groups than slots."""
    layout: Dict[int, List[int]] = defaultdict(list)
    if not iids or n_slots <= 0:
        return layout
    cap = max(1, cap)
    prio = _slot_priority(n_slots, stride)
    groups = [iids[i:i + cap] for i in range(0, len(iids), cap)]
    for gi, grp in enumerate(groups):
        layout[prio[gi % len(prio)]].extend(grp)
    return layout


def _distribute_perslot(iids: List[int], n_slots: int, caps: List[int],
                        stride: int) -> Dict[int, List[int]]:
    """Like ``_distribute`` but each slot has its OWN capacity (``caps[slot]``),
    because a 32x32x8 gap holds more than a 16x16x16 gap. Fills slots in
    ``_slot_priority`` order up to each slot's cap, wrapping only if fillers
    outnumber the total measured capacity."""
    layout: Dict[int, List[int]] = defaultdict(list)
    if not iids or n_slots <= 0:
        return layout
    prio = _slot_priority(n_slots, stride)
    i = 0
    while i < len(iids):
        progressed = False
        for s in prio:
            if i >= len(iids):
                break
            cap = max(1, caps[s])
            take = iids[i:i + cap]
            if take:
                layout[s].extend(take)
                i += len(take)
                progressed = True
        if not progressed:                    # safety: never spin forever
            break
    return layout


def _policy(kind: str, constraints: List[Dict], variant: str,
            mfma_class: Optional[str] = None) -> Tuple[int, int]:
    """(cap, stride) for placing ``kind`` (optionally for a specific MFMA shape).
    ``variant`` in {base, pack, spread}. pack => favour per_slot_capacity (more
    per slot, neighbours allowed); spread => favour adjacency (one per slot, skip
    neighbours)."""
    cap_c = _capacity(constraints, kind, mfma_class)
    coc = _cooccur(constraints, kind)
    avoid_adj = bool(coc and coc.get("polarity") == "avoid")
    median = int(round((cap_c or {}).get("stat", {}).get("median", 0)))
    cap_max = int(round((cap_c or {}).get("stat", {}).get("max", median or 1)))

    if variant == "pack":
        return max(1, cap_max), 1
    if variant == "spread":
        return 1, 2
    # base: respect the typical (median) capacity and the adjacency polarity.
    return max(1, median), (2 if avoid_adj else 1)


# ---------------------------------------------------------------------------
# Scoring: how many measured constraints does a layout satisfy (weighted)?
# ---------------------------------------------------------------------------
def _per_slot_counts(layout: Dict[int, List[int]],
                     kind_of: Dict[int, str]) -> Dict[int, Counter]:
    out: Dict[int, Counter] = {}
    for slot, iids in layout.items():
        c: Counter = Counter()
        for iid in iids:
            c[kind_of.get(iid, "?")] += 1
        out[slot] = c
    return out


def _adjacent_has(slot_counts: Dict[int, Counter], kind: str) -> bool:
    slots = sorted(slot_counts)
    return any(slot_counts[a].get(kind) and slot_counts[b].get(kind)
               for a, b in zip(slots, slots[1:]) if b == a + 1)


def _score(layout: Dict[int, List[int]], kind_of: Dict[int, str],
           constraints: List[Dict], present_kinds: set,
           confidence: float) -> Tuple[float, List[str]]:
    sc = _per_slot_counts(layout, kind_of)
    score = 0.0
    sat: List[str] = []
    for c in constraints:
        # score against the canonical POOLED constraints only; the per-MFMA-class
        # and per-width refinements steer placement (caps) but must not double-count.
        if c.get("mfma_class") or c.get("width"):
            continue
        w = float(c.get("weight", 0.0)) * confidence
        m = c.get("metric")
        kind = c.get("kind")
        ok = False
        if m == "per_slot_capacity":
            mx = max((cnt.get(kind, 0) for cnt in sc.values()), default=0)
            stat_max = c.get("stat", {}).get("max", mx)
            need = max(1, int(round(c.get("stat", {}).get("median", 0))))
            within = mx <= stat_max
            used = (mx >= need) if kind in present_kinds else True
            ok = within and used
        elif m == "adjacent_cooccur":
            has_adj = _adjacent_has(sc, kind)
            ok = (not has_adj) if c.get("polarity") == "avoid" else True
        elif m == "mfma_gap_size":
            stat_max = c.get("stat", {}).get("max")
            totals = [sum(cnt.values()) for cnt in sc.values()] or [0]
            ok = stat_max is None or max(totals) <= stat_max
        elif m == "intra_gap_order":
            ok = True            # satisfied by construction (we order each slot)
        if ok:
            score += w
            sat.append(c.get("metric") + (":" + kind if kind else ""))
    return round(score, 3), sat


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def plan_candidate_layouts(n_slots: int, fillers: List[Dict],
                           constraints: List[Dict],
                           conflict_groups: Optional[List[List[str]]] = None,
                           *, confidence: float = 1.0,
                           max_candidates: int = 4,
                           gap_classes: Optional[List[str]] = None) -> List[Dict]:
    """Generate up to ``max_candidates`` ranked candidate gap layouts.

    Args:
      n_slots: number of MFMA gaps (``len(anchors) - 1``).
      fillers: ``[{"iid": int, "kind": str, "movable": bool}, ...]`` -- the
        movable non-MFMA instructions to place (immovable ones are ignored).
      constraints / conflict_groups: straight from ``prior_plan`` (a quant skill).
      confidence: multiplier applied to every constraint weight (e.g. the mean
        confidence of the skills used); does not change ranking order on its own.
      gap_classes: optional per-gap MFMA shape (``["16x16x16","32x32x8",...]``,
        length ``n_slots``). When supplied, each gap's filler capacity is sized
        from the constraints measured for ITS shape (so a high-latency 32x32x8
        gap is packed fuller than a 16x16x16 gap) instead of one pooled capacity.

    Returns a list of ``{"layout": {slot: [iid,...]}, "score": float,
    "satisfied": [...], "rationale": str}`` sorted by score desc. Empty when the
    region is not MFMA-anchored (``n_slots < 1``) or has no movable fillers."""
    conflict_groups = conflict_groups or []
    movable = [f for f in fillers if f.get("movable", True)]
    # nothing to CONSUME without measured constraints; the planner never invents
    # a layout out of thin air (that would violate the "numbers measured" line).
    if n_slots < 1 or not movable or not constraints:
        return []
    use_classes = bool(gap_classes) and len(gap_classes) == n_slots

    kind_of = {f["iid"]: f["kind"] for f in movable}
    by_kind: Dict[str, List[int]] = defaultdict(list)
    for f in movable:
        by_kind[f["kind"]].append(f["iid"])
    present_kinds = set(by_kind)
    rank = _order_rank(constraints)

    # kinds that the conflict groups put in tension -> enumerate pack vs spread.
    conflict_kinds: List[str] = []
    for grp in conflict_groups:
        for member in grp:
            if ":" in member:
                k = member.split(":", 1)[1]
                if k in present_kinds and k not in conflict_kinds:
                    conflict_kinds.append(k)

    # variant assignments: cartesian product of {pack, spread} over conflict
    # kinds, plus always a "base" assignment. Bounded so we never explode.
    assignments: List[Dict[str, str]] = [{}]               # base: all kinds "base"
    for k in conflict_kinds:
        nxt: List[Dict[str, str]] = []
        for a in assignments:
            for v in ("pack", "spread"):
                a2 = dict(a)
                a2[k] = v
                nxt.append(a2)
        assignments = nxt
    # base assignment first, then the conflict variants
    if conflict_kinds:
        assignments = [{}] + assignments

    seen_layouts = set()
    out: List[Dict] = []
    for assign in assignments:
        layout: Dict[int, List[int]] = defaultdict(list)
        notes: List[str] = []
        for kind, iids in sorted(by_kind.items()):
            variant = assign.get(kind, "base")
            if use_classes:
                # stride is a cross-slot (adjacency) property -> pooled; cap is
                # sized per gap from that gap's own MFMA shape.
                _, stride = _policy(kind, constraints, variant)
                caps = [_policy(kind, constraints, variant, gap_classes[s])[0]
                        for s in range(n_slots)]
                placed = _distribute_perslot(iids, n_slots, caps, stride)
                notes.append("%s:%s(caps=%s,stride=%d)"
                             % (kind, variant, caps, stride))
            else:
                cap, stride = _policy(kind, constraints, variant)
                placed = _distribute(iids, n_slots, cap, stride)
                notes.append("%s:%s(cap=%d,stride=%d)" % (kind, variant, cap, stride))
            for slot, group in placed.items():
                layout[slot].extend(group)
        # order each slot's fillers by the measured intra-gap precedence.
        for slot in layout:
            layout[slot].sort(key=lambda iid: (rank.get(kind_of[iid], 0), iid))
        final = {s: layout[s] for s in sorted(layout)}

        key = tuple((s, tuple(final[s])) for s in final)
        if key in seen_layouts:
            continue
        seen_layouts.add(key)
        score, sat = _score(final, kind_of, constraints, present_kinds, confidence)
        out.append({"layout": final, "score": score, "satisfied": sat,
                    "rationale": "; ".join(notes)})

    out.sort(key=lambda p: -p["score"])
    return out[:max_candidates]
