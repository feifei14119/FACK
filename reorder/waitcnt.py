"""Read-only waitcnt parsing + counter simulation (M1).

This does NOT rewrite anything. It exists to prove the engine can correctly
*read* an existing kernel's synchronization:
  - parse every wait instruction (numeric simm16, ``vmcnt(..) & lgkmcnt(..)``,
    plain ``lgkmcnt(0)``, and ``s_waitcnt_vscnt``) via the Target CounterModel
  - walk the instruction stream maintaining outstanding counts per counter
    (vm / lgkm / exp / vs), draining them at each wait
  - surface warnings for anything inconsistent (counter width exceeded, etc.)

M2 will reuse this simulation (plus the dependency graph) to *recompute* waits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import COUNTER_OF, Kind, Line, LineKind, Program
from . import regions

# WaitType -> counter name used by the CounterModel
_WAITTYPE_TO_COUNTER = COUNTER_OF


@dataclass
class WaitEvent:
    line_idx: int
    opcode: str
    before: Dict[str, int]
    targets: Dict[str, Optional[int]]
    after: Dict[str, int]


@dataclass
class SimResult:
    events: List[WaitEvent] = field(default_factory=list)
    final_outstanding: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.warnings


def simulate(program: Program, target) -> SimResult:
    """Forward-simulate the hardware counters over the .text instruction stream."""
    cm = target.counter_model()
    counters = list(cm.names)
    outstanding: Dict[str, int] = {c: 0 for c in counters}
    result = SimResult(final_outstanding=outstanding)

    items = regions._collect_code_items(program)
    for it in items:
        ln = it.line
        if ln.kind is not LineKind.INSTR or not ln.opcode:
            continue
        op = ln.opcode.lower()

        if cm.is_wait(op):
            spec = cm.parse_wait(op, ln.operands)
            before = dict(outstanding)
            for c in counters:
                tgt = spec.targets.get(c)
                if tgt is None:
                    continue
                # a wait target must be encodable within the counter's field
                if tgt > cm.width(c):
                    result.warnings.append(
                        "line {}: {} wait target {} exceeds counter width {} "
                        "(unencodable)".format(ln.idx, c, tgt, cm.width(c)))
                if outstanding[c] > tgt:
                    outstanding[c] = tgt
            result.events.append(WaitEvent(
                line_idx=ln.idx, opcode=op, before=before,
                targets=dict(spec.targets), after=dict(outstanding),
            ))
            continue

        wt = target.wait_type(op, ln.operands)
        counter = _WAITTYPE_TO_COUNTER.get(wt)
        if counter is not None:
            # NOTE: hardware counters saturate at their field width; having more
            # than ``width`` ops in flight is legal (a later wait still drains
            # them), so we track the true outstanding count without warning.
            outstanding[counter] += 1

    # anything still outstanding at the end of the kernel (informational)
    result.final_outstanding = dict(outstanding)
    return result


def parse_existing(program: Program, target) -> List[WaitEvent]:
    """Return the parsed targets of every wait instruction (no simulation drain)."""
    cm = target.counter_model()
    out: List[WaitEvent] = []
    for ln in program.instr_lines():
        if not ln.opcode:
            continue
        op = ln.opcode.lower()
        if cm.is_wait(op):
            spec = cm.parse_wait(op, ln.operands)
            out.append(WaitEvent(line_idx=ln.idx, opcode=op, before={},
                                 targets=dict(spec.targets), after={}))
    return out


# ---------------------------------------------------------------------------
# Score-based waitcnt RECOMPUTE framework (M4/M5).
#
# Model: a *register scoreboard*. Each asynchronous op (load / ds_read / ...) is
# one event of its counter type and gets a monotone sequence number; it records,
# for every destination register, "this reg is produced by event seq of counter
# C". A waitcnt C(n) means "wait until <= n events of C are still outstanding",
# i.e. it guarantees every event with seq <= issued[C]-1-n has completed. At a
# *use* of a register produced by an async event, we must wait until that event
# completes -> n = issued[C]-1-seq(producer).
#
# Why a scoreboard (not the dep graph): hardware counters protect *register
# writes by async ops*; reg tracking is both precise (no false MEM edges) and,
# crucially, extends across the loop back-edge -- a use at the top of the loop
# body naturally binds to the producer issued in the PREVIOUS iteration. The
# dep graph is single-iteration and cannot express loop-carried sync.
#
# LOOP-CARRIED waitcnt (the central case for every real kernel): in a software-
# pipelined loop the wait in iteration n drains iteration n-1's loads while n
# issues n+1's loads. ``compute_waits_loop`` virtually unrolls the body and
# iterates to a fixpoint so the steady-state (cross-iteration) counts are found.
#
# LDS round-trip: ``buffer_load ... lds`` (vm) fills LDS that a later ``ds_read``
# (lgkm) consumes -- a dependency through memory, invisible to reg tracking.
# M5: a Target-provided ``LdsModel`` resolves the multi-buffer (ping-pong /
# triple-buffer) structure statically so a ds_read binds to the lds-loads that
# fill the SPECIFIC buffer band it reads (not the same-group loads filling a
# different band). When the model is absent/unresolved we fall back to the
# conservative single-bucket guard (a ds_read waits for the newest outstanding
# lds-direct load) -- always correct, possibly over-tight.
# ---------------------------------------------------------------------------

# WaitType -> whether the op's result is register-carried (counter-protected).
def _event_counter(target, line) -> Optional[str]:
    wt = target.wait_type(line.opcode or "", line.operands)
    return _WAITTYPE_TO_COUNTER.get(wt)


def _is_lds_direct_load(op: str, operands: List[str]) -> bool:
    return op.startswith("buffer_load") and any(
        str(o).strip().lower() == "lds" for o in operands)


def _lds_fill_counter(target, op: str, operands) -> Optional[str]:
    """Counter on which ``op`` asynchronously FILLS LDS from global memory
    (gfx942 ``buffer_load ... lds`` -> vm)."""
    hook = getattr(target, "lds_fill_counter", None)
    if hook is not None:
        return hook(op, operands)
    return "vm" if target.is_lds_load(op, operands) else None


def _reads_lds(target, op: str, operands) -> bool:
    hook = getattr(target, "reads_lds", None)
    if hook is not None:
        return hook(op, operands)
    return target.classify(op, operands) is Kind.DS_READ


def _is_branch_op(target, ln) -> bool:
    hook = getattr(target, "is_branch", None)
    return bool(hook(ln)) if hook is not None else False


def is_barrier_release(target, op: str, operands) -> bool:
    """The barrier op at which this wave's LDS accesses must be complete
    (gfx942 ``s_barrier``)."""
    if target.classify(op, operands) is not Kind.BARRIER:
        return False
    hook = getattr(target, "is_barrier_release", None)
    return hook(op) if hook is not None else True


def _order_group(target, op: str, operands):
    """Completion-order group of an async event: events of one counter return
    in order only WITHIN a target-defined group."""
    hook = getattr(target, "event_order_group", None)
    return hook(op, operands) if hook is not None else None


class _Scoreboard:
    """Register scoreboard for waitcnt recompute (see module header).

    Counter-name policy comes from the CounterModel hooks (``cm``); the defaults
    reproduce gfx942 (lgkm barrier drain / lgkm out-of-order SMEM).
    """

    def __init__(self, counters, lds_roundtrip: bool = True, lds_model=None,
                 barrier_band_scoped: bool = True, cm=None):
        self.counters = list(counters)
        self.lds_roundtrip = lds_roundtrip
        self.lds_model = lds_model
        # OptLevel knob: barrier fence drains only the read-bands (True) vs ALL
        # outstanding lds-loads (False, more robust). See reorder.optlevel.
        self.barrier_band_scoped = barrier_band_scoped
        self.barrier_drain = [c for c in getattr(cm, "barrier_drain_counters", ("lgkm",))
                              if c in self.counters]
        self.smem_counter = getattr(cm, "smem_counter", "lgkm")
        self.waw_sync = bool(getattr(cm, "waw_sync", False))
        self.fill_war = getattr(cm, "lds_fill_war_counter", None)
        if self.fill_war not in self.counters:
            self.fill_war = None
        # seed-derived sync contract (see SyncContract) replaces the band model
        self.contract = getattr(lds_model, "contract", None)
        self._contract_steady = self.contract
        self._contract_first = getattr(lds_model, "first", None)
        self.tracked = getattr(lds_model, "tracked", None) or set()
        self.issued = {c: 0 for c in self.counters}
        self.done = {c: -1 for c in self.counters}      # max completed seq
        self.prod: Dict = {}                            # reg -> (counter, seq)
        # outstanding LDS-fill seqs per fill counter (gfx942: only "vm")
        self.lds_seq: Dict[str, List[int]] = {}
        # SMEM (scalar memory: s_load / s_buffer_load / s_store / s_atomic) share
        # the lgkm counter with LDS BUT return OUT OF ORDER, whereas LDS returns
        # in order. A staged ``lgkmcnt(k>0)`` therefore cannot prove any specific
        # scalar-load result is back (nor keep a later LDS read's staged count
        # meaningful) while scalar mem ops are outstanding -- only ``lgkmcnt(0)``
        # (full drain) can. ``smem_live`` = lgkm seqs of scalar-mem ops not yet
        # guaranteed complete; it is cleared ONLY by a full lgkm drain.
        self.smem_live: set = set()
        # buffer-precise: buffer index -> outstanding (fill counter, seq)
        self.lds_bufs: Dict[int, List[Tuple[str, int]]] = {}
        # barrier line.idx -> set of LDS bands read before the NEXT barrier
        # (None entry == unresolved -> drain all). Empty/missing -> drain all.
        self.barrier_bands: Dict[int, Optional[set]] = {}
        # newest LDS-reading event on the fill-WAR counter
        self.lds_read_max = -1
        # counter -> [(seq, order group)] for counters with split order groups
        self.groups: Dict[str, List[Tuple[int, object]]] = {}
        # contract-tracked op iid -> [(counter, seq)] issue history
        self.hist: Dict[int, List[Tuple[str, int]]] = {}
        # completion frontier at the last branch (see issue())
        self._snap: Optional[Tuple[Dict[str, int], set]] = None

    def _live_fill(self, cand, need: Dict[str, int]) -> None:
        for c, s in cand:
            if s > self.done[c]:
                need[c] = max(need.get(c, -1), s)

    def _all_fills(self):
        return [(c, s) for c, seqs in self.lds_seq.items() for s in seqs]

    def first_iteration(self, on: bool) -> None:
        """While stepping a loop body's first iteration, hold its consumers to
        the seed's first-iteration contract."""
        if self._contract_steady is not None and self._contract_first is not None:
            self.contract = self._contract_first if on else self._contract_steady

    def _contract_need(self, ln, need: Dict[str, int]) -> None:
        for x, rank in self.contract.get(ln.idx, {}).items():
            h = self.hist.get(x)
            if h and len(h) >= rank:
                c, s = h[-rank]
                if s > self.done[c] or (c == self.smem_counter and s in self.smem_live):
                    need[c] = max(need.get(c, -1), s)

    def step(self, ln, target) -> Dict[str, int]:
        """Process one instruction; return the wait spec needed *before* it."""
        op = (ln.opcode or "").lower()
        defs, uses = target.def_use(op, ln.operands)
        kind = target.classify(op, ln.operands)

        need: Dict[str, int] = {}                       # counter -> max producer seq
        for r in uses:
            p = self.prod.get(r)
            if p is None:
                continue
            c, s = p
            if s > self.done[c]:
                need[c] = max(need.get(c, -1), s)
        if self.waw_sync:
            # overwriting a register an async op of ANOTHER counter (or an
            # out-of-order one) may still write back
            cev = _event_counter(target, ln)
            for r in defs:
                p = self.prod.get(r)
                if p is None:
                    continue
                c, s = p
                if s > self.done[c] and (c != cev or c == self.smem_counter):
                    need[c] = max(need.get(c, -1), s)
        if self.lds_roundtrip and self.contract is not None:
            # memory-carried LDS ordering reproduced from the seed's own waits
            self._contract_need(ln, need)
        elif self.lds_roundtrip and _reads_lds(target, op, ln.operands):
            # LDS round-trip: an LDS read must see the fills that wrote LDS
            buf = None
            if self.lds_model is not None and self.lds_model.resolved:
                buf = self.lds_model.read_buffer(ln.idx)
            if buf is not None:
                # buffer-precise: only the lds-loads that fill THIS band
                cand = self.lds_bufs.get(buf, ())
            else:
                # conservative fallback: every outstanding lds-direct load
                cand = self._all_fills()
            self._live_fill(cand, need)

        # BARRIER LDS-release fence: an ``s_barrier`` synchronizes all waves of
        # the workgroup, so every LDS access this wave issued before it must be
        # complete or another wave may read LDS this wave has not finished
        # writing (ds_write -> lgkm; buffer_load...lds -> vm). This is a
        # control/memory-ordering constraint, NOT a register dep, so it is
        # invisible to scoreboard tracking and must be added explicitly.
        #
        # lgkm: drained fully (all ds_*/smem done -> lgkmcnt(0)).
        # vm:   only the lds-direct loads of the bands actually READ before the
        #       next barrier need to complete (other bands' loads are prefetch
        #       for a LATER barrier and may stay in flight). ``barrier_bands``
        #       (precomputed look-ahead) names those bands; absent/None -> drain
        #       ALL outstanding lds-loads (conservative). Each wave drains its
        #       OWN copy of those bands, so this is sufficient cross-wave. The
        #       band-scoped form reproduces the hand-tuned ``vmcnt(N)`` (it keeps
        #       the other buffers' prefetch in flight); the all-drain form is
        #       tighter (safe, less overlap).
        if kind is Kind.BARRIER and is_barrier_release(target, op, ln.operands):
            # a seed sync contract already pins what the barrier needs; the
            # blanket drain is kept only as the L0 (conservative) behaviour
            for c in (self.barrier_drain if self.contract is None
                      or not self.barrier_band_scoped else ()):
                if self.issued[c] - 1 > self.done[c]:
                    need[c] = max(need.get(c, -1), self.issued[c] - 1)
            if self.contract is None:
                bands = self.barrier_bands.get(ln.idx, None)
                if self.barrier_band_scoped and ln.idx in self.barrier_bands \
                        and bands is not None:
                    # L1+: band look-ahead -- drain only the read-bands' loads
                    cand = [cs for b in bands for cs in self.lds_bufs.get(b, ())]
                else:
                    # L0 (conservative) / no look-ahead / unresolved: drain ALL
                    cand = self._all_fills()
                self._live_fill(cand, need)

        # LDS fill WAR: an async global->LDS write may not overtake this wave's
        # outstanding LDS reads before an asynchronous fill.
        # A sync contract already carries the seed's (band-aware) version.
        if self.fill_war is not None and self.contract is None \
                and _lds_fill_counter(target, op, ln.operands) is not None \
                and self.lds_read_max > self.done[self.fill_war]:
            need[self.fill_war] = max(need.get(self.fill_war, -1), self.lds_read_max)

        # SMEM out-of-order guard: if this consumer needs an lgkm result while ANY
        # scalar-mem op is still outstanding, a staged lgkmcnt is unsafe (the
        # counter may drain via unordered scalar-mem returns, not the op we need).
        # Force a full lgkm drain -- exactly what the source toolchain emits
        # (``s_waitcnt lgkmcnt(0)``) before consuming a scalar load.
        sc = self.smem_counter
        if sc in need and self.smem_live:
            need[sc] = self.issued[sc] - 1
        # split order groups (as declared by the target): a staged count
        # cannot prove a specific event once >1 group is in flight -> drain.
        for c in list(need):
            g = self.groups.get(c)
            if g and len({grp for (s, grp) in g if s > self.done[c]}) > 1:
                need[c] = self.issued[c] - 1

        spec: Dict[str, int] = {}
        for c, smax in need.items():
            n = self.issued[c] - 1 - smax
            spec[c] = n if n > 0 else 0
            if smax > self.done[c]:
                self.done[c] = smax
            if c == sc and spec[c] == 0:
                self.smem_live.clear()          # full drain -> all scalar mem done

        self.issue(ln, target)
        return spec

    def unmet_uses(self, ln, target):
        """Return [(reg, counter, producer_seq)] for register deps NOT yet
        guaranteed complete (used by the verifier; reg-carried deps only)."""
        op = (ln.opcode or "").lower()
        _, uses = target.def_use(op, ln.operands)
        out = []
        for r in uses:
            p = self.prod.get(r)
            if p is None:
                continue
            c, s = p
            # a scalar-mem (out-of-order) producer is only guaranteed done by a
            # full lgkm drain: if its seq is still in smem_live it is UNMET even
            # if a later staged lgkm wait advanced the in-order done frontier.
            if s > self.done[c] or (c == self.smem_counter and s in self.smem_live):
                out.append((r, c, s))
        return out

    def unmet_lds(self, ln, target):
        """Return ``(counter, seq)`` of an LDS-carried producer of ``ln`` NOT yet
        guaranteed complete by the applied waits (else None). With a sync
        contract every op is checked against it; otherwise only LDS reads (band
        precise when the model is resolved, else the conservative bucket)."""
        need: Dict[str, int] = {}
        if self.contract is not None:
            self._contract_need(ln, need)
        else:
            if not _reads_lds(target, (ln.opcode or "").lower(), ln.operands):
                return None
            cand = None
            if self.lds_model is not None and self.lds_model.resolved:
                buf = self.lds_model.read_buffer(ln.idx)
                if buf is not None:
                    cand = self.lds_bufs.get(buf, ())
            if cand is None:
                cand = self._all_fills()
            self._live_fill(cand, need)
        if not need:
            return None
        c = sorted(need)[0]
        return c, need[c]

    def unmet_barrier(self):
        """For a barrier, return [(counter, producer_seq)] for the LDS-release
        fence that is NOT yet satisfied. We assert ``lgkmcnt(0)`` -- all ds_*/
        smem ops must complete before an ``s_barrier`` so other waves observe a
        consistent LDS. (This is universally required and catches the classic
        ``lgkmcnt(3)``-before-barrier under-sync.) The vm side -- draining the
        lds-direct loads whose data is consumed right after the barrier -- is a
        cross-wave property the single-wave verifier can't pin precisely without
        false-positives on legitimately-in-flight prefetch loads, so it is
        enforced at GENERATION time, not asserted here."""
        out = []
        for c in self.barrier_drain:
            if self.issued[c] - 1 > self.done[c]:
                out.append((c, self.issued[c] - 1))
        return out

    def apply_wait(self, targets: Dict[str, Optional[int]]) -> None:
        """Advance completion frontier per an EXISTING wait's parsed targets."""
        for c, t in targets.items():
            if t is None or c not in self.counters:
                continue
            self.done[c] = max(self.done[c], self.issued[c] - t - 1)
            if c == self.smem_counter and t == 0:
                self.smem_live.clear()          # full drain -> all scalar mem done

    def issue(self, ln, target) -> None:
        """Account this instruction's async event (if any) + set reg producers."""
        op = (ln.opcode or "").lower()
        defs, _ = target.def_use(op, ln.operands)
        cev = _event_counter(target, ln)
        if cev in self.counters:
            seq = self.issued[cev]
            for r in defs:
                self.prod[r] = (cev, seq)
            fc = _lds_fill_counter(target, op, ln.operands)
            if fc is not None and fc == cev:
                self.lds_seq.setdefault(cev, []).append(seq)
                if self.lds_model is not None and self.contract is None:
                    buf = self.lds_model.write_buffer(ln.idx)
                    if buf is not None:
                        self.lds_bufs.setdefault(buf, []).append((cev, seq))
            if cev == self.fill_war and _reads_lds(target, op, ln.operands):
                self.lds_read_max = seq
            if cev == self.smem_counter and target.classify(op, ln.operands) is Kind.SMEM:
                self.smem_live.add(seq)         # scalar mem returns out of order
            grp = _order_group(target, op, ln.operands)
            if grp is not None:
                self.groups.setdefault(cev, []).append((seq, grp))
            if ln.idx in self.tracked:
                self.hist.setdefault(ln.idx, []).append((cev, seq))
            self.issued[cev] += 1
        else:
            for r in defs:                              # synchronous write -> ready
                self.prod[r] = None
        # A linear walk falls through s_endpgm into code reached only by jumps;
        # waits of the dead-end block (e.g. the drain before s_endpgm) must not
        # count for it, so roll the completion frontier back to the last branch.
        if op.startswith("s_endpgm"):
            if self._snap is not None:
                self.done, self.smem_live = dict(self._snap[0]), set(self._snap[1])
        elif _is_branch_op(target, ln):
            self._snap = (dict(self.done), set(self.smem_live))


class SyncContract:
    """Seed-derived memory-ordering contract (architecture-agnostic LDS model).

    When the LDS addressing of the fill ops cannot be resolved statically (e.g.
    copies whose LDS address lives in a VGPR / descriptor),
    the known-correct seed's OWN waits are the oracle: for every consumer ``Y``
    (an LDS-accessing op or a barrier) and every tracked async producer ``X``
    on a different counter, the seed guarantees the ``rank``-th newest issued
    instance of ``X`` has completed when ``Y`` issues. Recompute reproduces
    exactly those guarantees (``rank`` > 1 = pipelined distance), so prefetch
    depth survives without band modelling. Ranks stay meaningful under reorder:
    MEM edges pin the relative order of LDS writers/readers, barriers are
    fences, and edits never cross regions.

    ``contract``: consumer iid -> {producer iid: rank}; ``tracked``: producers.
    ``first``: the same for loop-body consumers in the FIRST iteration (the
    seed's guarantees there can be weaker than in steady state: producers
    issued before the loop are still in flight).
    ``depth``: the largest rank, i.e. how many loop iterations a checker must
    unroll before every requirement is observable.
    """

    resolved = False

    def __init__(self, contract: Dict[int, Dict[int, int]], tracked: set,
                 first: Optional[Dict[int, Dict[int, int]]] = None, depth: int = 1):
        self.contract = contract
        self.tracked = tracked
        self.first = first
        self.depth = depth

    def read_buffer(self, _idx):
        return None

    def write_buffer(self, _idx):
        return None


def derive_sync_contract(program: Program, target, is_producer, is_consumer,
                         max_loop_passes: int = 8) -> SyncContract:
    """Walk ``program`` applying its EXISTING waits; at every consumer record the
    newest guaranteed-complete instance rank of each tracked producer.

    ``is_producer(ln)`` / ``is_consumer(ln)`` select the memory-carried ops.
    Loop bodies are walked repeatedly (up to ``max_loop_passes``) until the
    recorded ranks stop changing, so loop-carried ranks reflect steady state
    even for producers prefetched several iterations ahead.
    """
    cm = target.counter_model()
    items = regions._collect_code_items(program)
    instr = [it.line for it in items if it.line.kind is LineKind.INSTR]
    tracked = {ln.idx for ln in instr
               if not cm.is_wait((ln.opcode or "").lower()) and is_producer(ln)
               and _event_counter(target, ln) in cm.names}
    board = _Scoreboard(cm.names, lds_roundtrip=False, cm=cm)
    board.tracked = tracked
    contract: Dict[int, Dict[int, int]] = {}
    try:
        a = regions.analyze(program, target)
        loop_spans = [(lp.header_pos, lp.tail_pos) for lp in a.loops
                      if 0 <= lp.header_pos <= lp.tail_pos < len(items)]
    except Exception:
        loop_spans = []

    first: Dict[int, Dict[int, int]] = {}

    def record(ln, into):
        my_c = _event_counter(target, ln)
        req = into.setdefault(ln.idx, {})
        for x, h in board.hist.items():
            if x == ln.idx or not h or (my_c is not None and h[-1][0] == my_c):
                continue                        # same counter completes in order
            for rank in range(1, len(h) + 1):
                c, s = h[-rank]
                if s <= board.done[c] and not (
                        c == board.smem_counter and s in board.smem_live):
                    if x not in req or rank < req[x]:
                        req[x] = rank
                    break

    def walk(seq_items, rec):
        for it in seq_items:
            ln = it.line
            if ln.kind is not LineKind.INSTR:
                continue
            op = (ln.opcode or "").lower()
            if cm.is_wait(op):
                board.apply_wait(cm.parse_wait(op, ln.operands).targets)
                continue
            if rec is not None and is_consumer(ln):
                record(ln, rec)
            board.issue(ln, target)

    i, n = 0, len(items)
    while i < n:
        span = next(((sp, ep) for (sp, ep) in loop_spans if sp <= i <= ep), None)
        if span is None:
            walk([items[i]], rec=contract)
            i += 1
            continue
        sp, ep = span
        body = items[sp:ep + 1]
        walk(body, rec=first)
        # a producer prefetched N iterations ahead is only guaranteed complete
        # in its N-th newest instance: unroll until the steady ranks settle
        prev, cur = None, {}
        for _ in range(max(1, max_loop_passes - 1)):
            cur = {}
            walk(body, rec=cur)
            if cur == prev:
                break
            prev = cur
        contract.update(cur)
        i = ep + 1
    contract = {k: v for k, v in contract.items() if v}
    depth = max((r for req in contract.values() for r in req.values()), default=1)
    return SyncContract(contract, tracked, first={k: v for k, v in first.items() if v},
                        depth=depth)


def _barrier_read_bands(instr_lines: List, target, lds_model) -> Dict[int, Optional[set]]:
    """Map each barrier's ``line.idx`` -> the set of LDS bands read between it and
    the NEXT barrier (cyclically, since the body repeats across the loop back-edge).

    The barrier's vm release-fence only needs to drain those bands; other bands'
    lds-loads are prefetch consumed after a later barrier. A ``None`` value means
    "a read in the segment couldn't be band-resolved -> drain ALL" (conservative).
    Returns ``{}`` when the LDS model is unresolved (caller then drains all).
    """
    if lds_model is None or not getattr(lds_model, "resolved", False):
        return {}
    n = len(instr_lines)
    is_bar = [target.classify((ln.opcode or "").lower(), ln.operands) is Kind.BARRIER
              for ln in instr_lines]
    bar_pos = [i for i, b in enumerate(is_bar) if b]
    if not bar_pos:
        return {}
    out: Dict[int, Optional[set]] = {}
    for pos in bar_pos:
        bands: set = set()
        unresolved = False
        j, steps = (pos + 1) % n, 0
        while steps < n and not is_bar[j]:
            ln = instr_lines[j]
            if target.classify((ln.opcode or "").lower(), ln.operands) is Kind.DS_READ:
                b = lds_model.read_buffer(ln.idx)
                if b is None:
                    unresolved = True
                else:
                    bands.add(b)
            j, steps = (j + 1) % n, steps + 1
        out[instr_lines[pos].idx] = None if unresolved else bands
    return out


def compute_waits(instr_lines: List, target, board: Optional["_Scoreboard"] = None,
                  lds_roundtrip: bool = True, lds_model=None,
                  barrier_band_scoped: bool = True
                  ) -> Dict[int, Dict[str, int]]:
    """Single straight-line pass: ``{consumer_iid: {counter: target}}``."""
    cm = target.counter_model()
    if board is None:
        board = _Scoreboard(cm.names, lds_roundtrip=lds_roundtrip, lds_model=lds_model,
                            barrier_band_scoped=barrier_band_scoped, cm=cm)
        board.barrier_bands = _barrier_read_bands(instr_lines, target, lds_model)
    need: Dict[int, Dict[str, int]] = {}
    for ln in instr_lines:
        spec = board.step(ln, target)
        if spec:
            need[ln.idx] = spec
    return need


def compute_waits_loop(instr_lines: List, target, max_copies: int = 8,
                       lds_roundtrip: bool = True, lds_model=None,
                       barrier_band_scoped: bool = True,
                       return_board: bool = False,
                       board: Optional["_Scoreboard"] = None,
                       ) -> Dict[int, Dict[str, int]]:
    """Loop-aware: virtually unroll the body and iterate to a fixpoint so that
    loop-carried (cross-iteration) waits reach steady state.

    Returns the steady-state ``{consumer_iid: {counter: target}}`` for one body.
    With ``return_board=True`` returns ``(need, board)`` where ``board`` holds the
    steady-state EXIT scoreboard (its outstanding loads etc. are what a following
    region -- e.g. the epilogue -- must drain; see ``recompute_cfg``).

    ``board`` seeds the loop ENTRY with ops still in flight from before the
    loop. Every copy then runs the same emitted code, so the result is the
    strictest target per counter over all copies, not just the last one."""
    cm = target.counter_model()
    seeded = board is not None
    if board is None:
        board = _Scoreboard(cm.names, lds_roundtrip=lds_roundtrip, lds_model=lds_model,
                            barrier_band_scoped=barrier_band_scoped, cm=cm)
    board.barrier_bands = _barrier_read_bands(instr_lines, target, lds_model)
    prev_key = None
    last: Dict[int, Dict[str, int]] = {}
    union: Dict[int, Dict[str, int]] = {}
    # rank-N contract requirements only surface from the N-th copy on
    depth = getattr(board.lds_model, "depth", 1) if board.contract is not None else 1
    min_copies = depth + 1
    max_copies = max(max_copies, min_copies)
    for copy in range(max_copies):
        board.first_iteration(seeded and copy == 0)
        cur: Dict[int, Dict[str, int]] = {}
        for ln in instr_lines:
            spec = board.step(ln, target)
            if spec:
                cur[ln.idx] = spec
                u = union.setdefault(ln.idx, {})
                for c, v in spec.items():
                    u[c] = min(u.get(c, v), v)
        key = {k: tuple(sorted(v.items())) for k, v in cur.items()}
        if prev_key is not None and key == prev_key and copy >= min_copies:
            break
        prev_key = key
        last = cur
    else:
        cur = last
    board.first_iteration(False)
    need = union if seeded else cur
    return (need, board) if return_board else need


def _entry_board(items, end_line: int, target, cm, **kw) -> "_Scoreboard":
    """Scoreboard after running the code before ``end_line`` once, straight
    line, honouring its existing waits."""
    board = _Scoreboard(cm.names, cm=cm, **kw)
    pre = [it for it in items if it.line.idx < end_line]
    for it in pre:
        ln = it.line
        if ln.kind is not LineKind.INSTR:
            continue
        op = (ln.opcode or "").lower()
        if cm.is_wait(op):
            board.apply_wait(cm.parse_wait(op, ln.operands).targets)
        else:
            board.issue(ln, target)
    return board


def _snapshot(board: "_Scoreboard") -> "_Scoreboard":
    """Independent copy of a scoreboard; the read-only LDS model / contracts
    are shared, not copied."""
    import copy
    memo = {}
    for shared in (board.lds_model, board.contract, board._contract_steady,
                   board._contract_first, board.tracked):
        if shared is not None:
            memo[id(shared)] = shared
    return copy.deepcopy(board, memo)


def _walk_path(items, start: int, board, target, cm, stop_at_branch: bool):
    """Step ``board`` along code items from ``start`` (code-item pos) in program
    order, honouring existing waits, until a program end (or, with
    ``stop_at_branch``, an unconditional branch). Yields ``(line, spec)``."""
    for it in items[start:]:
        ln = it.line
        if ln.kind is not LineKind.INSTR:
            continue
        op = (ln.opcode or "").lower()
        if cm.is_wait(op):
            board.apply_wait(cm.parse_wait(op, ln.operands).targets)
            continue
        yield ln, board.step(ln, target)
        if regions._is_program_end(ln, target):
            return
        if stop_at_branch and target.is_branch(ln) and target.is_terminator(ln):
            return


def _seed_loop_boards(items, lo: int, hi: int, entry, target, cm, exits,
                      copies: int = 4):
    """Steady-state boards of the SEED loop body (its existing waits honoured):
    ``({branch_idx: board at that side exit}, board at the fallthrough exit)``."""
    board = entry
    at_exit = {}
    for copy in range(copies):
        board.first_iteration(copy == 0)
        for it in items[lo:hi + 1]:
            ln = it.line
            if ln.kind is not LineKind.INSTR:
                continue
            op = (ln.opcode or "").lower()
            if cm.is_wait(op):
                board.apply_wait(cm.parse_wait(op, ln.operands).targets)
                continue
            board.step(ln, target)
            if copy == copies - 1 and ln.idx in exits:
                at_exit[ln.idx] = _snapshot(board)
    board.first_iteration(False)
    return at_exit, board


def _loop_exit_guard(items, region, body_lines, exit_board, seed_entry, target, cm):
    """Waits a loop recompute must add OUTSIDE the loop.

    The loop pass only syncs consumers inside the body, so a wait the seed had
    in the body for a consumer after the loop (fallthrough exit) or on a side
    exit (branch out of the body, e.g. a cold tail) can disappear. Each exit
    path is walked twice -- from the new steady-state board and from the seed
    loop's steady-state board -- and only the extra demand of the new order is
    kept, so an unchanged loop leaves the code outside it untouched."""
    label_pos = {it.line.label: it.pos for it in items
                 if it.line.kind is LineKind.LABEL and it.line.label}
    span = [it.pos for it in items
            if region.line_start <= it.line.idx <= region.line_end]
    lo, hi = min(span), max(span)

    exits = {}
    for ln in body_lines:
        if target.is_branch(ln):
            tgt = target.branch_target(ln)
            p = label_pos.get(tgt)
            if p is not None and not (lo <= p <= hi + 1):
                exits[ln.idx] = p
    seed_entry.barrier_bands = exit_board.barrier_bands
    seed_at, seed_exit = _seed_loop_boards(items, lo, hi, seed_entry, target, cm, exits)

    paths = []                       # (start pos, new board, seed board, stop_at_branch)
    if exits:
        walk = _snapshot(exit_board)
        for ln in body_lines:
            walk.step(ln, target)
            if ln.idx in exits:
                paths.append((exits[ln.idx], _snapshot(walk), seed_at[ln.idx], True))
    latch = body_lines[-1]
    if not (target.is_branch(latch) and target.is_terminator(latch)):
        paths.append((hi + 1, exit_board, seed_exit, False))

    extra: Dict[int, Dict[str, int]] = {}
    for start, new, seed, stop in paths:
        old_specs = {ln.idx: s for ln, s in _walk_path(items, start, seed, target, cm, stop)}
        for ln, spec in _walk_path(items, start, new, target, cm, stop):
            old = old_specs.get(ln.idx, {})
            for c, v in spec.items():
                if c not in old or v < old[c]:
                    e = extra.setdefault(ln.idx, {})
                    e[c] = min(e.get(c, v), v)
    return extra


def _make_line(idx: int, indent: str, opcode: str, operands: List[str], body: str):
    raw = "{}{} {}".format(indent, opcode, body) if body else indent + opcode
    return Line(idx=idx, raw=raw, kind=LineKind.INSTR, indent=indent,
                opcode=opcode, operands=operands)


def recompute(program: Program, target, region=None,
              scope_line_idxs: Optional[set] = None,
              loop_aware: Optional[bool] = None,
              lds_roundtrip: bool = True,
              opt_level=None):
    """Drop existing waits in scope and insert recomputed waits.

    Mutates ``program.lines`` in place and returns the new line list. ``region``
    (a regions.Region) or ``scope_line_idxs`` limits the scope; default = the
    whole ``.text`` instruction stream.

    ``loop_aware`` forces the fixpoint (cross-iteration) recompute; when None it
    is auto-enabled for a region whose kind is ``loop`` (the common, critical
    case -- a straight-line linear pass is INCORRECT for a pipelined loop).

    ``opt_level`` (see ``reorder.optlevel``) selects the barrier LDS-release
    fence aggressiveness: L0 drains ALL outstanding lds-loads at each barrier
    (robust to band-model error), L1+ drains only the bands read before the next
    barrier (band look-ahead, keeps other prefetch in flight). Default = L1.
    """
    from reorder import optlevel as _opt
    pol = _opt.policy(_opt.DEFAULT if opt_level is None else opt_level)
    barrier_band_scoped = pol.barrier_band_scoped
    cm = target.counter_model()
    items = regions._collect_code_items(program)
    text_idxs = {it.line.idx for it in items}

    if loop_aware is None:
        loop_aware = bool(region is not None
                          and getattr(region.kind, "value", None) == "loop")

    if region is not None:
        scope = {it.line.idx for it in items
                 if region.line_start <= it.line.idx <= region.line_end}
    elif scope_line_idxs is not None:
        scope = set(scope_line_idxs) & text_idxs
    else:
        scope = set(text_idxs)

    instr_lines = [it.line for it in items
                   if it.line.idx in scope and it.line.kind is LineKind.INSTR
                   and not cm.is_wait((it.line.opcode or "").lower())]

    # LDS round-trip slot model (M5): supplied by the Target when it can resolve
    # the multi-buffer structure; reorder/ stays architecture-agnostic. Fold
    # over the whole .text prefix (the LDS base chain lives in the prologue) but
    # only record loads/reads in scope.
    lds_model = None
    if lds_roundtrip and hasattr(target, "lds_roundtrip_model"):
        text_instr = [it.line for it in items if it.line.kind is LineKind.INSTR]
        lds_model = target.lds_roundtrip_model(text_instr, scope_idxs=scope)

    if loop_aware:
        kw = dict(lds_roundtrip=lds_roundtrip, lds_model=lds_model,
                  barrier_band_scoped=barrier_band_scoped)
        seeded = region is not None and getattr(cm, "seed_loop_entry", False)
        entry = _entry_board(items, region.line_start, target, cm, **kw) if seeded else None
        if region is not None and instr_lines:
            seed_entry = (_snapshot(entry) if entry is not None
                          else _Scoreboard(cm.names, cm=cm, **kw))
        need, exit_board = compute_waits_loop(
            instr_lines, target, lds_roundtrip=lds_roundtrip, lds_model=lds_model,
            barrier_band_scoped=barrier_band_scoped, board=entry, return_board=True)
        if region is not None and instr_lines:
            for idx, spec in _loop_exit_guard(items, region, instr_lines, exit_board,
                                              seed_entry, target, cm).items():
                cur = need.setdefault(idx, {})
                for c, v in spec.items():
                    cur[c] = min(cur.get(c, v), v)
    else:
        need = compute_waits(instr_lines, target, lds_roundtrip=lds_roundtrip,
                             lds_model=lds_model,
                             barrier_band_scoped=barrier_band_scoped)

    return _emit_need(program, cm, need, scope)


def _emit_need(program, cm, need: Dict[int, Dict[str, int]], scope: set) -> List:
    """Drop existing waits in ``scope`` and insert the recomputed ``need`` waits
    immediately before each consumer. Mutates ``program.lines`` in place."""
    next_idx = max((ln.idx for ln in program.lines), default=0) + 1
    new_lines: List = []
    for ln in program.lines:
        op = (ln.opcode or "").lower()
        in_scope = ln.idx in scope
        if in_scope and ln.kind is LineKind.INSTR and cm.is_wait(op):
            continue  # drop the old wait; we own synchronization now
        if ln.idx in need:
            spec = need[ln.idx]
            indent = ln.indent or "  "
            for opcode, operands, body in cm.format_waits(spec):
                new_lines.append(_make_line(next_idx, indent, opcode, operands, body))
                next_idx += 1
        new_lines.append(ln)

    program.lines = new_lines
    return new_lines


def recompute_cfg(program, target, opt_level=None, lds_roundtrip: bool = True):
    """Whole-kernel multi-region recompute with a BOUNDARY counter contract.

    Recomputes every region in program order, threading one scoreboard across
    region boundaries so cross-region in-flight async ops are honoured:

      * prologue / inter / epilogue : straight-line pass, SEEDED with the
        preceding region's exit scoreboard (prologue starts empty = kernel entry).
      * loop : loop-aware fixpoint (self-contained, HW-validated). Its steady-
        state EXIT scoreboard seeds the next region -- this is what fixes the
        epilogue's ds_read / barrier LDS-release fence, whose producing lds-loads
        were issued inside the loop (invisible to an isolated epilogue recompute).

    barrier count is preserved; only s_waitcnt / s_waitcnt_vscnt are rewritten.
    """
    from reorder import optlevel as _opt
    pol = _opt.policy(_opt.DEFAULT if opt_level is None else opt_level)
    bbs = pol.barrier_band_scoped
    cm = target.counter_model()
    items = regions._collect_code_items(program)
    text_instr = [it.line for it in items if it.line.kind is LineKind.INSTR]
    text_idxs = {ln.idx for ln in text_instr}

    lds_model = None
    if lds_roundtrip and hasattr(target, "lds_roundtrip_model"):
        lds_model = target.lds_roundtrip_model(text_instr, scope_idxs=text_idxs)
    barrier_bands = _barrier_read_bands(text_instr, target, lds_model)

    a = regions.analyze(program, target)
    regs = sorted(a.regions, key=lambda r: r.line_start)

    def region_instr(r):
        return [ln for ln in text_instr
                if r.line_start <= ln.idx <= r.line_end
                and not cm.is_wait((ln.opcode or "").lower())]

    all_need: Dict[int, Dict[str, int]] = {}
    board = None                       # exit scoreboard of the previous region
    for r in regs:
        rlines = region_instr(r)
        if not rlines:
            continue
        if getattr(r.kind, "value", None) == "loop":
            need, board = compute_waits_loop(
                rlines, target, lds_roundtrip=lds_roundtrip, lds_model=lds_model,
                barrier_band_scoped=bbs, return_board=True,
                board=board if getattr(cm, "seed_loop_entry", False) else None)
        else:
            if board is None:
                board = _Scoreboard(cm.names, lds_roundtrip=lds_roundtrip,
                                    lds_model=lds_model, barrier_band_scoped=bbs, cm=cm)
                board.barrier_bands = barrier_bands
            else:
                board.barrier_bands = barrier_bands
            need = compute_waits(rlines, target, board=board,
                                 lds_roundtrip=lds_roundtrip, lds_model=lds_model,
                                 barrier_band_scoped=bbs)
        all_need.update(need)

    return _emit_need(program, cm, all_need, set(text_idxs))
