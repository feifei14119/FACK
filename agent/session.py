"""M7 LLM decision surface: let an LLM agent (Cursor agent or any model) DRIVE
the fixed-logic engine through three clean, low-frequency moves -- without ever
adjudicating legality (that stays in the engine + Verifier + real-HW gate).

This is the closed loop documented in ``proj/if/ai_interface.md`` §3.4.3, made
callable as one object:

    sess = AgentSession(seed_src, evaluator)
    obs  = sess.observe()                      # READ the facts map (JSON-able)
    rep  = sess.propose([{0:[ld0,ld1], 2:[ld2]}])   # TRY layouts (non-committing)
    res  = sess.commit_and_eval({0:[ld0,ld1], 2:[ld2]})  # MEASURE on real HW (gated)

The LLM reads ``obs`` (per-slot layout, instruction kinds, legal windows, latency
edges, recognised prefetch loads to NOT scatter, voted direction prior, and any
knowledge-seeded prior), reasons with its own hardware knowledge, proposes
non-uniform layouts, reads back ``SkipReason`` feedback, and only commits a layout
that the engine deems legal -- the verdict is measured TFLOPS + correctness.

Every commit is appended to the experiments log so the (non-deterministic) agent
decisions stay traceable (design §4), while the inner build/eval stays reproducible.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence

from reorder import cost as cost_mod, parser, regions
from reorder.editor import RegionEditor
from reorder.model import COUNTER_OF, Kind
from harness.measurement import measure_screen, valid_score

from search import driver
from . import knowledge as kn
from . import layout_planner
from .artifacts import save_assembly

# async counter (CounterModel short name) each WaitType maps to
_WAITTYPE_TO_COUNTER = COUNTER_OF


# --- observation (the read-only "facts map" the LLM reads) ------------------
@dataclass
class SlotView:
    slot: int                       # MFMA-gap index
    anchor_iid: int                 # the MFMA bounding the slot's start
    fillers: List[Dict] = field(default_factory=list)   # [{iid, kind}] in the gap


@dataclass
class FillerView:
    iid: int
    kind: str
    legal_window: Sequence[int]     # (lo, hi) positions it may occupy
    movable: bool
    is_prefetch: bool               # recognised cross-iteration prefetch (hoist-only)


@dataclass
class NodeView:
    """One instruction of an ANCHOR-LESS region (no MFMA), as a DAG node. This is
    the prologue/epilogue counterpart of SlotView/FillerView: there are no MFMA
    gaps to fill, so the agent reasons over the dependency DAG directly and
    reorders the whole region (see proj/anchorless_region_scheduling.md)."""

    iid: int
    kind: str
    pos: int                        # position in the region's current order
    legal_window: Sequence[int]     # (lo, hi) positions it may occupy
    movable: bool
    is_fence: bool                  # pinned (barrier/exec-write/branch)
    bumps_counter: Optional[str] = None     # async counter this op increments (vm/lgkm/exp/vs)
    waits_on: Optional[Dict] = None         # {counter: target} if this is a wait
    preds: List[Sequence[int]] = field(default_factory=list)  # [(iid, dist), ...]
    succs: List[Sequence[int]] = field(default_factory=list)


@dataclass
class Observation:
    anchors: List[int]                                  # MFMA iids (slot boundaries)
    slots: List[SlotView] = field(default_factory=list)
    fillers: List[FillerView] = field(default_factory=list)  # movable non-MFMA ops
    latency_edges: List[Sequence[int]] = field(default_factory=list)  # (a,b,dist) dist>1
    prefetch_loads: List[int] = field(default_factory=list)
    direction: Optional[Dict] = None                    # voted bottleneck prior
    prior_plan: Optional[Dict] = None                   # knowledge-seeded specs/avoid/note
    regions: List[Dict] = field(default_factory=list)   # all detected regions (selectable)
    region: Optional[str] = None                        # the region this view describes
    dag: Optional[List[Dict]] = None                    # anchor-less DAG view (no MFMA): NodeView[]
    tunable: Optional[List[int]] = None                 # anchor-less: the small "worth-moving"
                                                        # subset of dag iids (movable + on the
                                                        # critical path or bumps an async counter)
    segments: Optional[List[Dict]] = None               # anchor-less: fence-bounded segments
                                                        # [{seg_id, iids, est_cycles}] -- tune the
                                                        # costliest small segment, not the whole region
    critical: Optional[Dict] = None                     # anchor-less: {top_k, dominant_wait} focus
    waitcnt_preview: Optional[Dict] = None              # current-order waits + RegionCost
    phases: Optional[List[Dict]] = None                 # anchored / anchorless phases of the
                                                        # region (reorder.phases); anchor-less
                                                        # phases of a mixed region carry their
                                                        # own dag/tunable/segments/critical

    def to_dict(self) -> Dict:
        return {
            "anchors": self.anchors,
            "slots": [asdict(s) for s in self.slots],
            "fillers": [asdict(f) for f in self.fillers],
            "latency_edges": [list(e) for e in self.latency_edges],
            "prefetch_loads": self.prefetch_loads,
            "direction": self.direction,
            "prior_plan": self.prior_plan,
            "regions": self.regions,
            "region": self.region,
            "dag": self.dag,
            "tunable": self.tunable,
            "segments": self.segments,
            "critical": self.critical,
            "waitcnt_preview": self.waitcnt_preview,
            "phases": self.phases,
        }


class _SubOrder:
    """Read-only view of an editor restricted to a contiguous sub-order (one
    phase), for the anchor-less helpers that only read ``order`` / ``_fences`` /
    ``_line_of`` / ``target``."""

    def __init__(self, ed, iids: List[int]) -> None:
        self.order = list(iids)
        self._fences = ed._fences
        self._line_of = ed._line_of
        self.target = ed.target


# --- propose feedback (structured, so the LLM can iterate) ------------------
@dataclass
class ProposeOutcome:
    layout: Dict[int, List[int]]
    placed: List[Dict] = field(default_factory=list)    # [{iid, slot}]
    skipped: List[Dict] = field(default_factory=list)    # [{iid, slot, reason, window, bound_iid}]
    legal: bool = False


@dataclass
class CommitResult:
    layout: Dict[int, List[int]]
    correct: Optional[bool]
    tflops: Optional[float]
    accepted: bool          # beat baseline beyond the noise margin?
    baseline_tflops: Optional[float]
    note: str = ""
    est_cycles: Optional[int] = None            # cost-model proxy for the candidate
    baseline_est_cycles: Optional[int] = None   # ...and the baseline (region-local)
    stage: str = "screen"          # legacy accepted is not independent confirmation
    verdict: str = "inconclusive"
    evidence: Dict = field(default_factory=dict)


class AgentSession:
    """Stateful driver bound to one seed kernel + one evaluator. The seed text is
    never mutated in place; each operation builds a fresh editor so observe/
    propose are side-effect-free and reproducible."""

    def __init__(self, seed_src: str, evaluator, *, context: Optional[Dict] = None,
                 store: str = kn.DEFAULT_STORE, out_store: Optional[str] = None,
                 perf_repeats: int = 3,
                 direction_captures: int = 5, noise_margin: float = 0.0,
                 protect_prefetch: bool = True, region: str = "loop",
                 loop_trips: Optional[int] = None,
                 max_order_intent: int = 64,
                 tunable_top_k: int = 8, tunable_window_min: int = 1):
        self.seed_src = seed_src
        self.evaluator = evaluator
        self.context = context or {}
        # ``store`` is READ for the knowledge prior (curated knowledge/engine by
        # default). ``out_store`` is WRITTEN to for the experiments log; it falls
        # back to a temporary output store for the curated default. Explicit
        # custom stores retain the legacy single-store behaviour.
        self.store = store
        self.out_store = (out_store if out_store is not None else
                          kn.DEFAULT_OUT_STORE if store == kn.DEFAULT_STORE else store)
        self.perf_repeats = perf_repeats
        self.direction_captures = direction_captures
        self.noise_margin = noise_margin
        self.protect_prefetch = protect_prefetch
        # which code region the agent is currently tuning: "loop" (default, the
        # MFMA-heaviest loop), "prologue", "epilogue", "inter", "body",
        # "outlined", an indexed form ("loop#1") or "loop@<label>".
        self.region = region
        # runtime trip count of the LOOP region(s) at the target shape (from K /
        # unroll, injected by the caller). Drives est_share so the agent spends
        # budget on the region that dominates THIS shape (small K -> prologue/
        # epilogue can dominate). None = unknown -> est_share left None.
        self.loop_trips = loop_trips
        # soft guardrail against the anchor-less full-order propose collapse:
        # a --order intent longer than this is rejected in O(1) with a hint to
        # use a PARTIAL order (see proj/brainstorm/anchorless_fullorder_propose_perf.md).
        self.max_order_intent = max_order_intent
        # anchor-less "worth-moving" subset knobs (proj/brainstorm/large_dag_finetune.md
        # direction 1): a node is tunable if it is movable, its legal window is at
        # least this wide, AND it is on the critical path (top-K by chain length)
        # or bumps an async counter (vm/lgkm -- the latency-hiding memory ops).
        self.tunable_top_k = tunable_top_k
        self.tunable_window_min = tunable_window_min
        self._baseline_tflops: Optional[float] = None
        self._baseline_path: Optional[str] = None
        self._baseline_checked = False
        self._baseline_evidence: Dict = {}
        self._original_evidence: Dict = {}
        self.last_archive = None

    # --- internal: a fresh editor over the SELECTED region -----------------
    def _editor(self):
        prog = parser.parse(self.seed_src)
        t = driver._default_target(prog)
        regs = regions.analyze(prog, t).regions
        region = regions.select_region(regs, self.region, prog, t)
        return RegionEditor(prog, t, region, treat_waitcnt_as_fence=False,
                            protect_prefetch=self.protect_prefetch)

    # --- internal: JSON-able list of ALL regions + the selected kind -------
    def list_regions(self):
        prog = parser.parse(self.seed_src)
        t = driver._default_target(prog)
        regs = regions.analyze(prog, t).regions
        summaries = regions.region_summaries(prog, regs)
        # shape-aware "where is the time": est_share = trip_count * est_cycles.
        # loop trip_count from self.loop_trips (target shape); others run once.
        for s, r in zip(summaries, regs):
            s["est_cycles"] = cost_mod.estimate(prog, t, r).est_cycles
            if r.kind is regions.RegionKind.OUTLINED:
                trips = None            # cold tails / specialised copies: shape-dependent
            else:
                trips = self.loop_trips if r.kind.value == "loop" else 1
            s["trip_count"] = trips
            s["est_share"] = (trips * s["est_cycles"]) if trips is not None else None
        sel = regions.select_region(regs, self.region, prog, t)
        return summaries, sel.kind.value

    # --- 1) OBSERVE: the read-only facts map -------------------------------
    def observe(self, *, with_direction: bool = True) -> Observation:
        ed = self._editor()
        region_summaries, selected_kind = self.list_regions()
        g = ed.graph
        pos = {i: k for k, i in enumerate(ed.order)}
        anchors = ed.anchors(Kind.MFMA)
        pf = ed.prefetch_info()

        slots: List[SlotView] = []
        for s in range(len(anchors) - 1):
            lo, hi = pos[anchors[s]], pos[anchors[s + 1]]
            fillers = [{"iid": ed.order[p], "kind": ed.kind_of(ed.order[p]).value}
                       for p in range(lo + 1, hi)]
            slots.append(SlotView(s, anchors[s], fillers))

        fillers: List[FillerView] = []
        for iid in ed.order:
            k = ed.kind_of(iid)
            if k is Kind.MFMA:
                continue
            win = g.legal_window(iid)
            fillers.append(FillerView(iid, k.value, list(win), win[1] > win[0],
                                      iid in pf.producers))

        cm = ed.target.counter_model()

        def _counter_of(iid: int) -> Optional[str]:
            ln = ed._line_of[iid]
            return _WAITTYPE_TO_COUNTER.get(
                ed.target.wait_type((ln.opcode or "").lower(), ln.operands))

        def _waits_on(iid: int) -> Optional[Dict]:
            ln = ed._line_of[iid]
            op = (ln.opcode or "").lower()
            if not (op and cm.is_wait(op)):
                return None
            spec = cm.parse_wait(op, ln.operands)
            return {c: t for c, t in spec.targets.items() if t is not None}

        # Anchor-less region (no MFMA): the slot model degenerates, so expose the
        # dependency DAG directly -- the agent reorders the whole region rather
        # than filling MFMA gaps (proj/anchorless_region_scheduling.md §4.1).
        # A mixed region (e.g. GEMM -> softmax -> GEMM) gets the same view per
        # anchor-less PHASE instead (proj/mixed_loop_scheduling.md P1).
        def anchorless_view(iids: List[int]) -> Dict:
            sub = _SubOrder(ed, iids)
            dag = []
            windows: Dict[int, Sequence[int]] = {}
            for iid in iids:
                lo, hi = g.legal_window(iid)
                windows[iid] = (lo, hi)
                dag.append(asdict(NodeView(
                    iid=iid, kind=ed.kind_of(iid).value, pos=pos[iid],
                    legal_window=[lo, hi], movable=hi > lo,
                    is_fence=iid in ed._fences,
                    bumps_counter=_counter_of(iid), waits_on=_waits_on(iid),
                    preds=sorted([p, g.dist(p, iid)] for p in g.preds(iid)),
                    succs=sorted([s, g.dist(iid, s)] for s in g.succs(iid)))))
            return {
                "dag": dag,
                "tunable": self._tunable_subset(
                    g, iids, windows, _counter_of,
                    ed.target.counter_model().latency_counters),
                "segments": self._fence_segments(sub),
                "critical": self._critical_focus(sub, g, windows),
            }

        dag = None
        tunable: Optional[List[int]] = None
        segments: Optional[List[Dict]] = None
        critical: Optional[Dict] = None
        if not anchors:
            v = anchorless_view(list(ed.order))
            dag, tunable, segments, critical = (v["dag"], v["tunable"],
                                                v["segments"], v["critical"])
        phase_views = self._phase_views(ed, anchors, anchorless_view)

        # waitcnt preview: current-order waits in the region + the cost-model
        # scalar, so the agent sees what a reorder is up against (and after a
        # propose, whether est_cycles dropped). Cheap + GPU-less (§4.1/§4.3).
        rc = cost_mod.estimate(ed.program, ed.target, ed.region)
        preview_waits: List[Dict] = []
        for ln in regions.region_instr_lines(ed.program, ed.region):
            w = _waits_on(ln.idx)
            if w:
                for c, t in w.items():
                    preview_waits.append({"at_iid": ln.idx, "counter": c, "target": t})
        waitcnt_preview = {"waits": preview_waits, "cost": rc.to_dict()}

        direction = None
        if with_direction:
            try:
                base_path = self._ensure_baseline()
                vote = driver.vote_direction(self.evaluator, base_path,
                                             self.direction_captures)
                direction = {"bottleneck": vote.bottleneck,
                             "confidence": vote.confidence, "votes": vote.votes,
                             "trusted": vote.trusted()}
            except Exception as e:                       # evaluator may be GPU-less
                direction = {"error": str(e)}

        prior = None
        try:
            prior = kn.seed_search_plan(dict(self.context, region=self.region),
                                        self.store)
        except Exception:
            prior = None

        return Observation(
            anchors=anchors, slots=slots, fillers=fillers,
            latency_edges=[list(e) for e in g.latency_edges()],
            prefetch_loads=sorted(pf.producers),
            direction=direction, prior_plan=prior,
            regions=region_summaries, region=selected_kind, dag=dag,
            tunable=tunable, segments=segments, critical=critical,
            waitcnt_preview=waitcnt_preview, phases=phase_views)

    def _phase_views(self, ed, anchors: List[int], anchorless_view) -> List[Dict]:
        """Per-phase map of the region (reorder.phases): anchored phases list the
        slot indices they own; anchor-less phases of a MIXED region carry their
        own dag / tunable / segments / critical (a fully anchor-less region keeps
        those at the top level). Every phase gets the counter-based est_cycles
        and, when the Target has an issue model,
        ``issue_cycles``."""
        from reorder import phases as _ph
        slot_of = {a: s for s, a in enumerate(anchors)}
        issue_model = getattr(ed.target, "issue_cycles", None)
        out: List[Dict] = []
        for ph in _ph.split_phases(ed.order, anchors):
            iids = list(ed.order[ph.lo:ph.hi + 1])
            lines = [ed._line_of[i] for i in iids]
            v: Dict = {"index": ph.index, "kind": ph.kind, "lo": ph.lo, "hi": ph.hi,
                       "size": ph.size, "anchors": list(ph.anchors),
                       "fences": sum(1 for i in iids if i in ed._fences),
                       "est_cycles": cost_mod.estimate_lines(lines, ed.target).est_cycles}
            if issue_model is not None:
                v["issue_cycles"] = issue_model(lines)
            if ph.kind == _ph.ANCHORED:
                v["slots"] = [slot_of[a] for a in ph.anchors[:-1]]
            else:
                before = [a for a in anchors if a in ed.order[:ph.lo]]
                after = [a for a in anchors if a in ed.order[ph.hi + 1:]]
                v["replaces_slot"] = slot_of[before[-1]] if before and after else None
                if anchors:
                    v.update(anchorless_view(iids))
            out.append(v)
        if anchors:
            self._phase_migration(ed, anchors, out)
        return out

    def _phase_migration(self, ed, anchors: List[int], views: List[Dict]) -> None:
        """Cross-phase moves at each anchor-less phase boundary, within ONE
        iteration (proj/mixed_loop_scheduling.md P2): which of its instructions
        may legally enter which slots of the neighbouring anchored phases
        (``to_prev`` / ``to_next``: [{iid, kind, slots}]), and which fillers of
        those phases may sink/hoist into it (``from_prev`` / ``from_next``).
        Uses the editor's real insertion range (existing waits are re-derived
        after the move, so they do not pin anything). Apply a move with an
        ordinary ``propose`` / ``eval --layout`` slot layout."""
        n_slots = len(anchors) - 1
        for k, v in enumerate(views):
            if v["kind"] != "anchorless":
                continue
            prev = views[k - 1] if k > 0 and views[k - 1]["kind"] == "anchored" else None
            nxt = views[k + 1] if k + 1 < len(views) and views[k + 1]["kind"] == "anchored" else None
            mig = {"to_prev": [], "to_next": [], "from_prev": [], "from_next": []}
            own = set(ed.order[v["lo"]:v["hi"] + 1])

            def reach(iid):
                # a slot layout places the unit right after anchors[s]
                unit = ed.unit(iid)
                lo, hi, order_wo = ed._block_insert_range(unit)
                at = {x: i for i, x in enumerate(order_wo)}
                slots = [s for s in range(n_slots) if lo <= at[anchors[s]] + 1 <= hi]
                return unit, lo, hi, order_wo, slots

            def rederived(iid):
                return ed.kind_of(iid) in (Kind.WAITCNT, Kind.NOP)

            seen = set()
            for iid in ed.order[v["lo"]:v["hi"] + 1]:
                if iid in ed._fences or iid in seen or rederived(iid):
                    continue
                unit, lo, hi, order_wo, slots = reach(iid)
                seen.update(unit)
                kind = ed.kind_of(iid).value
                for side, ph in (("to_prev", prev), ("to_next", nxt)):
                    if ph is None:
                        continue
                    hit = [s for s in slots if s in ph["slots"]]
                    if hit:
                        mig[side].append({"iid": iid, "kind": kind, "slots": hit})
            for side, ph in (("from_prev", prev), ("from_next", nxt)):
                if ph is None:
                    continue
                for iid in ed.order[ph["lo"]:ph["hi"] + 1]:
                    if iid in ed._fences or ed.kind_of(iid) is Kind.MFMA or iid in seen \
                            or rederived(iid):
                        continue
                    unit = ed.unit(iid)
                    seen.update(unit)
                    lo, hi, order_wo = ed._block_insert_range(unit)
                    inside = [i for i, x in enumerate(order_wo) if x in own]
                    if inside and lo <= inside[-1] and inside[0] <= hi:
                        mig[side].append({"iid": iid, "kind": ed.kind_of(iid).value})
            v["migration"] = mig

    def _fence_segments(self, ed) -> List[Dict]:
        """Split the anchor-less region into fence-bounded segments (the real
        optimization units -- instructions never move across a fence) and cost
        each one, so the agent tunes the COSTLIEST small segment instead of the
        whole region (proj/brainstorm/large_dag_finetune.md direction 2). Reuses
        the list-scheduler's segmentation + the region cost model."""
        from search import list_scheduler as _ls
        segs = _ls._segments(list(ed.order), ed._fences)
        out: List[Dict] = []
        seg_id = 0
        for seg in segs:
            if len(seg) == 1 and seg[0] in ed._fences:
                continue                                  # pinned fence singleton
            lines = [ed._line_of[i] for i in seg]
            rc = cost_mod.estimate_lines(lines, ed.target)
            out.append({"seg_id": seg_id, "iids": list(seg),
                        "est_cycles": rc.est_cycles})
            seg_id += 1
        return out

    def _critical_focus(self, ed, g, windows) -> Dict:
        """The 'where is the bottleneck' focus for an anchor-less region: the
        top-K movable nodes by critical-path length + the single wait that drains
        the most outstanding async ops (and which loads fed it). Turns the noisy
        anchor-less prior into an actionable shortlist (large_dag_finetune.md
        direction 3)."""
        from search import list_scheduler as _ls
        cp = _ls._critical_path(g, list(ed.order))
        movable = [i for i in ed.order if windows[i][1] > windows[i][0]]
        top_k = sorted(movable, key=lambda i: (-cp.get(i, 0), i))[:self.tunable_top_k]
        return {"top_k": top_k, "dominant_wait": self._dominant_wait(ed)}

    def _dominant_wait(self, ed) -> Optional[Dict]:
        """Walk the region's scoreboard and return the wait that drains the most
        outstanding async ops: {at_iid, counter, target, feeders[]}. ``feeders``
        are the iids (loads/stores) whose in-flight results that wait drained --
        i.e. what to schedule earlier to hide the stall."""
        cm = ed.target.counter_model()
        counters = list(cm.names)
        outstanding: Dict[str, List[int]] = {c: [] for c in counters}
        best = None
        for iid in ed.order:
            ln = ed._line_of[iid]
            op = (ln.opcode or "").lower()
            if not op:
                continue
            if cm.is_wait(op):
                spec = cm.parse_wait(op, ln.operands)
                drained = 0
                feeders: List[int] = []
                wc = None
                for c in counters:
                    tgt = spec.targets.get(c)
                    if tgt is None:
                        continue
                    if len(outstanding[c]) > tgt:
                        cut = len(outstanding[c]) - tgt
                        drained += cut
                        feeders.extend(outstanding[c][:cut])
                        outstanding[c] = outstanding[c][cut:]
                        if wc is None:
                            wc = c
                    elif wc is None:
                        wc = c
                if drained > 0 and (best is None or drained > best[0]):
                    best = (drained, {"at_iid": iid, "counter": wc,
                                      "target": spec.targets.get(wc),
                                      "feeders": sorted(feeders)})
                continue
            counter = _WAITTYPE_TO_COUNTER.get(
                ed.target.wait_type(op, ln.operands))
            if counter is not None:
                outstanding[counter].append(iid)
        return best[1] if best else None

    def _tunable_subset(self, graph, order, windows, counter_of,
                        latency_counters=("vm", "lgkm")) -> List[int]:
        """The "worth-moving" subset of an anchor-less region's nodes: shrink the
        full DAG (which can be hundreds of nodes) to the few the agent should
        actually reorder (proj/brainstorm/large_dag_finetune.md direction 1).

        A node qualifies when it is movable, its legal window is at least
        ``tunable_window_min`` wide, AND either it sits on the critical path
        (top-K by downstream chain length) or it bumps an async memory counter
        (vm/lgkm -- the latency-hiding loads/stores whose placement drives the
        stalls). Tight address chains (window width 1, movable=False) drop out."""
        from search import list_scheduler as _ls
        cp = _ls._critical_path(graph, list(order))
        movable = [i for i in order
                   if windows[i][1] - windows[i][0] >= max(1, self.tunable_window_min)]
        topk = set(sorted(movable, key=lambda i: (-cp.get(i, 0), i))
                   [:self.tunable_top_k])
        out: List[int] = []
        for iid in order:
            lo, hi = windows[iid]
            if hi - lo < max(1, self.tunable_window_min):
                continue
            if iid in topk or counter_of(iid) in latency_counters:
                out.append(iid)
        return out

    # --- 2) PROPOSE: try layouts WITHOUT committing ------------------------
    def propose(self, candidates: Sequence[Dict[int, List[int]]]
                ) -> List[ProposeOutcome]:
        ed = self._editor()
        anchors = ed.anchors(Kind.MFMA)
        reports = ed.propose_layouts(anchors, list(candidates))
        out: List[ProposeOutcome] = []
        for r in reports:
            out.append(ProposeOutcome(
                layout={int(k): list(v) for k, v in r.layout.items()},
                placed=[{"iid": p.iid, "slot": p.slot} for p in r.placed],
                skipped=[{"iid": p.iid, "slot": p.slot,
                          "reason": p.reason.value if p.reason else None,
                          "window": list(p.window), "bound_iid": p.bound_iid}
                         for p in r.skipped],
                legal=r.legal))
        return out

    # --- 2b) PROPOSE ORDERS: anchor-less linear-order intents (M9) ---------
    def propose_orders(self, candidates: Sequence[Sequence[int]]) -> List[Dict]:
        """Validate (partial/full) linear-order intents for an anchor-less region
        WITHOUT committing. Returns one JSON-able report per candidate with
        placed / skipped(reason+window+bound_iid) / legal / cost(est_cycles)."""
        ed = self._editor()
        reports = ed.propose_orders(list(candidates),
                                    max_intent=self.max_order_intent)
        out: List[Dict] = []
        for r in reports:
            row = {
                "order_intent": list(r.order_intent),
                "placed": [{"iid": p.iid} for p in r.placed],
                "skipped": [{"iid": p.iid,
                             "reason": p.reason.value if p.reason else None,
                             "window": list(p.window), "bound_iid": p.bound_iid}
                            for p in r.skipped],
                "legal": r.legal, "cost": r.cost}
            if r.error:
                row["error"] = r.error
            out.append(row)
        return out

    # --- 2b') SUGGEST: engine-generated seed orders (large-DAG leverage) ----
    def suggest_orders(self, n: int = 3, phase: Optional[int] = None) -> Dict:
        """Let the ENGINE generate a few legal seed reorders for an anchor-less
        region, so the agent chooses among 2-3 candidates instead of constructing
        a full N-element order from scratch (proj/brainstorm/large_dag_finetune.md
        direction 4). Runs the weighted list scheduler under a handful of weight
        presets (critical-path / latency / load-hoist biased), costs each with the
        GPU-less region cost model, and returns them ranked by est_cycles.

        Each entry: {weights, order, est_cycles}. The agent can commit one via
        commit_and_eval_order, or use it as a base and micro-tune with a partial
        --order over the tunable subset.

        ``phase`` restricts the reorder to one phase of a mixed region (see
        ``observe().phases``, e.g. the softmax between two GEMMs); the rest of
        the region keeps its order."""
        from search import list_scheduler as _ls
        ed = self._editor()
        g = ed.graph
        base = list(ed.order)
        base_cost = cost_mod.estimate(ed.program, ed.target, ed.region).est_cycles
        presets = [
            ("critical_path", _ls.Weights(critical_path=2.0, latency=0.5)),
            ("latency", _ls.Weights(critical_path=0.5, latency=2.0)),
            ("load_hoist", _ls.Weights(critical_path=1.0, load_hoist=2.0)),
        ][:max(1, n)]
        out: List[Dict] = []
        seen = {tuple(base)}
        for name, w in presets:
            order = _ls.schedule_phase(ed, w, phase)
            if not g.is_order_legal(order, fences=ed._fences):
                continue
            key = tuple(order)
            if key in seen:
                continue
            seen.add(key)
            ed.order = list(order)
            c = ed._materialized_region_cost()
            ed.order = list(base)
            out.append({"weights": name, "order": list(order),
                        "est_cycles": (c or {}).get("est_cycles")})
        out.sort(key=lambda r: (r["est_cycles"] is None, r["est_cycles"]))
        return {"baseline_est_cycles": base_cost, "candidates": out}

    # --- 2c) PLAN: constraint-driven candidate layouts (Layer 3) -----------
    def plan_layouts(self, *, max_candidates: int = 4,
                     validate: bool = True) -> List[Dict]:
        """Consume the gold-mined QUANT constraints in ``prior_plan`` and emit a
        ranked set of CANDIDATE gap layouts for THIS kernel's actual fillers
        (the Layer 3 constraint consumer, see proj/skill/ai_assisted_skill_mining.md).

        Pure navigation: layouts are generated from the MEASURED constraint stats
        (capacity / adjacency / gap-size / ordering) with conflict_groups expanded
        into pack-vs-spread variants. When ``validate`` (default), each candidate
        is run through :meth:`propose` so the caller sees ``legal`` + how many
        fillers actually placed -- still no hardware. The agent / search then
        commits the most promising legal candidate for a real-HW verdict."""
        obs = self.observe(with_direction=False)
        n_slots = max(0, len(obs.anchors) - 1)
        prior = obs.prior_plan or {}
        fillers = [{"iid": f.iid, "kind": f.kind, "movable": f.movable}
                   for f in obs.fillers]
        # per-gap MFMA shape: gap s is opened by anchor s, so its capacity should
        # be sized from the constraints measured for THAT shape (32x32x8 gaps hold
        # more than 16x16x16 gaps). Falls back to pooled sizing if unavailable.
        gap_classes = None
        if n_slots >= 1:
            ed = self._editor()
            gap_classes = [layout_planner.mfma_shape_class(ed.opcode_of(obs.anchors[s]))
                           for s in range(n_slots)]
        plans = layout_planner.plan_candidate_layouts(
            n_slots, fillers,
            prior.get("constraints", []), prior.get("conflict_groups", []),
            max_candidates=max_candidates, gap_classes=gap_classes)
        if not validate or not plans:
            return plans
        reports = self.propose([p["layout"] for p in plans])
        for p, r in zip(plans, reports):
            p["legal"] = r.legal
            p["n_placed"] = len(r.placed)
            p["n_skipped"] = len(r.skipped)
        return plans

    # --- 2d) LEARN: constraint-driven layouts with a HW-validation SWITCH ---
    def learn_layouts(self, *, validate: bool = False, max_candidates: int = 4,
                      promote: bool = False, learn: bool = True) -> Dict:
        """Run the gold-mined layout constraints through the closed loop, with a
        real-hardware validation SWITCH (proj/skill/ai_assisted_skill_mining.md L3).

        ``validate=False`` (default) -- OFFLINE: only derive + ``propose``-validate
          the candidate layouts (pure CPU; the evaluator is NEVER called). Use
          this to summarise skills for many architectures on ONE box without
          visiting each GPU machine.
        ``validate=True`` -- ONLINE: additionally ``commit_and_eval`` every legal
          candidate on real hardware (same correctness + Verifier + noise gate,
          logged to the experiments log); when ``promote`` also ``induce_and_save``
          so candidates corroborated by measured deltas can rise to ``trusted``.

        Returns a JSON-able summary: ``{"validated", "n_candidates", "n_legal",
        "candidates"[, "results", "best", "promoted"]}``."""
        plans = self.plan_layouts(max_candidates=max_candidates, validate=True)
        legal = [p for p in plans if p.get("legal")]
        out: Dict = {"validated": validate, "n_candidates": len(plans),
                     "n_legal": len(legal), "candidates": plans}
        if not validate:
            return out                       # offline: no hardware touched

        results: List[Dict] = []
        for p in sorted(legal, key=lambda x: -x["score"]):
            res = self.commit_and_eval(p["layout"], learn=learn)
            results.append({"layout": p["layout"], "score": p["score"],
                            "tflops": res.tflops, "correct": res.correct,
                            "accepted": res.accepted, "note": res.note})
        accepted = [r for r in results if r["accepted"]]
        out["results"] = results
        out["best"] = (max(accepted, key=lambda r: (r["tflops"] or 0.0))
                       if accepted else None)
        if promote:
            out["promoted"] = [s.id for s in kn.induce_and_save(self.out_store)]
        return out

    # --- 3) COMMIT + EVALUATE: real-HW verdict, gated + logged -------------
    def commit_and_eval(self, layout: Dict[int, List[int]], *,
                        learn: bool = True) -> CommitResult:
        spec = {"kind": "layout",
                "layout": {int(k): list(v) for k, v in layout.items()},
                "protect_prefetch": self.protect_prefetch,
                "region": self.region}
        return self._commit_spec(spec, layout, learn)

    def commit_and_eval_order(self, order: Sequence[int], *,
                              learn: bool = True) -> CommitResult:
        """Commit a linear-order intent (anchor-less region) on real HW, gated +
        logged -- the order counterpart of :meth:`commit_and_eval`."""
        order = [int(x) for x in order]
        spec = {"kind": "order", "order": order,
                "protect_prefetch": self.protect_prefetch, "region": self.region}
        return self._commit_spec(spec, {"order": order}, learn)

    def _commit_spec(self, spec: Dict, log_layout, learn: bool) -> CommitResult:
        self.last_archive = None
        text, ok = driver.build_candidate(self.seed_src, spec)
        evidence = {"schema_version": 1, "baseline_kind": "normalized",
                    "spec": spec, "static_ok": ok,
                    "evaluation_contract": self.context.get("evaluation_contract")}
        if not ok:
            res = CommitResult(log_layout, None, None, False,
                               self._baseline_tflops, "verify failed",
                               verdict="illegal", evidence=evidence)
            if learn:
                self._log(spec, res)
            return res
        # Preserve exact source identities BEFORE any expensive client call.
        artifact = save_assembly(text, self.out_store)
        evidence["candidate"] = {"artifact": artifact, "measurement": None}
        base_tf = self._measure_baseline()
        evidence["original"] = self._original_evidence
        evidence["normalized"] = self._baseline_evidence
        if base_tf is None:
            res = CommitResult(log_layout, None, None, False, None,
                               "normalized baseline did not pass screening",
                               verdict="baseline_failed", evidence=evidence)
            if learn:
                self._log(spec, res)
            return res
        self.last_archive = artifact["path"]
        path = self._write(text, "agent_layout")
        batch = measure_screen(self.evaluator, path, self.perf_repeats,
                               expected_sha256=artifact["sha256"])
        evidence["candidate"]["measurement"] = batch.to_dict()
        correct, tflops = batch.correct, batch.tflops
        cand_cost = self._region_cost(text)
        base_cost = self._baseline_region_cost()
        accepted, note = self._verdict(correct, tflops, base_tf,
                                       cand_cost, base_cost)
        res = CommitResult(log_layout, correct, tflops, accepted, base_tf, note,
                           est_cycles=cand_cost, baseline_est_cycles=base_cost,
                           verdict=(batch.status if batch.status != "measured" else
                                    "screening_gain" if tflops > base_tf * (1 + self.noise_margin) else
                                    "screening_regression" if tflops < base_tf * (1 - self.noise_margin) else
                                    "exploration_only" if accepted else "inconclusive"),
                           evidence=evidence)
        if batch.status != "measured":
            res.note = batch.error or batch.status
        self._archive_candidate(text, res)
        if learn:
            self._log(spec, res)
        return res

    def _archive_candidate(self, text: str, res: "CommitResult") -> None:
        """Keep a copy of every committed candidate .s under
        ``<out_store>/tune_shaders/`` (the per-round workdir .s is otherwise
        overwritten each commit). The filename encodes time + region + verdict +
        TFLOPS so runs are traceable. Best-effort: never breaks the eval. Each
        SDK round is a separate process, so a microsecond stamp + pid keeps names
        unique and ordered across rounds."""
        try:
            import os
            import time
            d = os.path.join(self.out_store, "tune_shaders")
            os.makedirs(d, exist_ok=True)
            region = str(self.region).replace("#", "_").replace("/", "_")
            verdict = ("incorrect" if res.correct is False
                       else "accepted" if res.accepted else "rejected")
            tf = ("%.3f" % res.tflops) if res.tflops is not None else "na"
            kernel = os.path.splitext(self.context.get("kernel") or "kernel")[0]
            now = time.time()
            stamp = time.strftime("%Y%m%d-%H%M%S",
                                  time.localtime(now)) + "-%06d" % (int(now * 1e6) % 1000000)
            name = "%s_%s_%s_%s_tf%s_pid%d.s" % (
                stamp, kernel, region, verdict, tf, os.getpid())
            full = os.path.join(d, name)
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            # Remember the exact archived path so the caller can record it in the
            # result row (lets the run finalizer copy the BEST .s with no guessing).
            self.last_archive = full
        except Exception:
            pass

    # --- shape-adaptive verdict (M9 §3.2) ----------------------------------
    def _verdict(self, correct, tflops, base_tf, cand_cost, base_cost):
        """Real-HW first; the cost model only breaks ties INSIDE the noise band
        and can NEVER overturn a measured regression or an incorrect result.

        - faster beyond noise   -> accept (this is what resolves small-trip
          shapes where prologue/epilogue directly move whole-kernel TFLOPS).
        - slower beyond noise / incorrect -> reject.
        - within the noise band -> accept iff the cost model improved (lower
          est_cycles): the gradient that keeps large-trip tail tuning from
          stalling when the tail's effect is below the TFLOPS noise floor."""
        if correct is not True:
            return False, "rejected: incorrect"
        if not valid_score(tflops) or not valid_score(base_tf):
            return False, "no measurement"
        hi = base_tf * (1.0 + self.noise_margin)
        lo = base_tf * (1.0 - self.noise_margin)
        if tflops > hi:
            return True, "accepted: faster beyond noise"
        if tflops < lo:
            return False, "rejected: slower beyond noise"
        if cand_cost is not None and base_cost is not None and cand_cost < base_cost:
            return True, ("accepted: within noise, lower est_cycles (%d<%d)"
                          % (cand_cost, base_cost))
        return False, "kept baseline: within noise, no est_cycles gain"

    def _region_cost(self, text: str) -> Optional[int]:
        """est_cycles of the SELECTED region in a built candidate (re-parsed)."""
        try:
            prog = parser.parse(text)
            t = driver._default_target(prog)
            regs = regions.analyze(prog, t).regions
            region = regions.select_region(regs, self.region, prog, t)
            return cost_mod.estimate(prog, t, region).est_cycles
        except Exception:
            return None

    def _baseline_region_cost(self) -> Optional[int]:
        if getattr(self, "_baseline_cost", None) is None:
            text = getattr(self, "_baseline_text", None)
            if text is None:
                self._measure_baseline()
                text = getattr(self, "_baseline_text", None)
            self._baseline_cost = self._region_cost(text) if text else None
        return self._baseline_cost

    # --- baseline / logging helpers ----------------------------------------
    def _ensure_baseline(self) -> str:
        if self._measure_baseline() is None:
            raise RuntimeError("normalized baseline did not pass screening")
        return self._baseline_path

    def _measure_baseline(self) -> Optional[float]:
        if self._baseline_checked:
            return self._baseline_tflops
        # Original is preserved, but NOT separately measured in this first
        # evidence-only phase. Never label normalized scores as original gains.
        self._original_evidence = {
            "artifact": save_assembly(self.seed_src, self.out_store),
            "measurement_status": "not_measured", "measurement": None}
        spec = {"kind": "ladder", "level": 1, "region": self.region}
        text, ok = driver.build_candidate(self.seed_src, spec)
        self._baseline_text = text
        artifact = save_assembly(text, self.out_store)
        self._baseline_evidence = {"artifact": artifact, "spec": spec,
                                   "static_ok": ok, "measurement": None}
        if not ok:
            self._baseline_checked = True
            return None
        self._baseline_path = self._write(text, "baseline")
        batch = measure_screen(self.evaluator, self._baseline_path,
                               self.perf_repeats, expected_sha256=artifact["sha256"])
        self._baseline_evidence["measurement"] = batch.to_dict()
        self._baseline_checked = True
        self._baseline_tflops = batch.tflops
        return self._baseline_tflops

    def _write(self, text: str, name: str) -> str:
        import os
        import tempfile
        d = getattr(self, "_workdir", None)
        if d is None:
            d = self._workdir = tempfile.mkdtemp(prefix="testft_agent_")
        p = os.path.join(d, "%s.s" % name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def _log(self, spec: Dict, res: CommitResult) -> None:
        try:
            transform = {k: v for k, v in spec.items() if k != "protect_prefetch"}
            kn.log_experiment({
                "kernel": self.context.get("kernel"),
                "shape": self.context.get("shape"),
                "arch": self.context.get("arch"),
                "loop_kind": self.context.get("loop_kind"),
                "scenario": self.context.get("scenario", "agent_layout"),
                "bottleneck": self.context.get("bottleneck"),
                "region": self.region,
                "transform": transform,
                "baseline_tflops": res.baseline_tflops,
                "tflops": res.tflops, "correct": res.correct,
                "est_cycles": res.est_cycles,
                "baseline_est_cycles": res.baseline_est_cycles,
                "stage": res.stage, "verdict": res.verdict,
                "evidence": res.evidence,
                "decided_by": "llm_agent",
            }, self.out_store)
        except Exception:
            pass
