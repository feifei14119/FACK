"""Final-line-of-defence verifier (architecture-agnostic core + Target invariants).

Runs BEFORE any expensive hardware test to filter broken candidates. Checks:
  1. dependency order   -- every dep edge a->b respected in program order
  2. waitcnt sufficiency -- every async memory producer a consumer depends on is
                            guaranteed complete by some wait before the consumer
                            (using the Target CounterModel + actual wait lines)
  3. architecture invariants -- e.g. gfx942 barrier-count-locked, via
                            ``Target.invariants()``

This is a static, GPU-free check; passing it does not replace the compile +
numerical-correctness backstop, it just avoids wasting GPU time on dead candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import regions
from .depgraph import DepGraph
from .model import LineKind, Program
from .waitcnt import _Scoreboard, _snapshot, is_barrier_release


@dataclass
class VerifyResult:
    ok: bool
    violations: List[str] = field(default_factory=list)


class _JumpEntry:
    """Entry state for code reached only by jumps (e.g. outlined blocks after
    ``s_endpgm``): the linear walk would otherwise carry in the state of
    whatever precedes it in the file. With exactly one branch seen into the
    label, its state is restored; otherwise the linear state is kept.
    Register checks only: SyncContract ranks are defined on the linear walk."""

    def __init__(self, target):
        self.target = target
        self.snaps = {}             # label -> {branch idx: board snapshot}
        self.dead = False           # previous instruction never falls through

    def label(self, ln, board) -> None:
        if self.dead:
            preds = self.snaps.get(ln.label, {})
            if len(preds) == 1:
                board.__dict__.update(_snapshot(next(iter(preds.values()))).__dict__)
        self.dead = False

    def instr(self, ln, board) -> None:
        t = self.target
        branch = t.is_branch(ln)
        if branch:
            tgt = t.branch_target(ln)
            if tgt:
                self.snaps.setdefault(tgt, {})[ln.idx] = _snapshot(board)
        self.dead = regions._is_program_end(ln, t) or (branch and t.is_terminator(ln))


class Verifier:
    def __init__(self, target, reference: Optional[Program] = None,
                 analysis=None):
        self.target = target
        self.reference = reference
        self.analysis = analysis        # regions.RegionAnalysis -> enables loop-aware check

    def verify(self, program: Program) -> VerifyResult:
        v: List[str] = []
        v += self._dep_order(program)
        v += self._waitcnt_sufficiency(program)
        v += self._lds_barrier_sufficiency(program)
        v += self._invariants(program)
        return VerifyResult(ok=not v, violations=v)

    # --- 1. dependency order ----------------------------------------------
    def _instr_stream(self, program):
        return [it.line for it in regions._collect_code_items(program)
                if it.line.kind is LineKind.INSTR]

    def _dep_order(self, program) -> List[str]:
        cm = self.target.counter_model()
        nonwait = [ln for ln in self._instr_stream(program)
                   if not cm.is_wait((ln.opcode or "").lower())]
        graph = DepGraph.build(nonwait, self.target)
        order = [ln.idx for ln in nonwait]
        if graph.is_order_legal(order):
            return []
        pos = {iid: i for i, iid in enumerate(order)}
        bad = [(a, b, t.value) for a, b, t in graph.edges()
               if pos.get(a, -1) >= pos.get(b, -1)]
        return ["dep order violated: {} edges (e.g. {})".format(len(bad), bad[:3])]

    # --- 2. waitcnt sufficiency (reg-carried deps; loop-aware) ------------
    #
    # Reads EXISTING waits and checks that every register produced by an async
    # op is guaranteed complete before each use. Reg-carried only: the
    # LDS-round-trip (buffer_load...lds -> ds_read) dep needs slot-precise m0
    # modelling to check minimally, so it is intentionally NOT asserted here to
    # avoid false positives (it is handled conservatively at *generation* time).
    def _waitcnt_sufficiency(self, program) -> List[str]:
        cm = self.target.counter_model()
        counters = list(cm.names)
        # Use code-item POSITIONS (robust to recompute-inserted lines whose idx
        # is out of the original loop's idx range). ``analysis`` must be built on
        # the CURRENT program for positions to align.
        items = regions._collect_code_items(program)
        loop_spans = []
        if self.analysis is not None:
            loop_spans = [(lp.header_pos, lp.tail_pos) for lp in self.analysis.loops
                          if 0 <= lp.header_pos <= lp.tail_pos < len(items)]

        board = _Scoreboard(counters, lds_roundtrip=False, cm=cm)
        violations: List[str] = []
        entry = _JumpEntry(self.target)

        def walk(seq_items, record):
            for it in seq_items:
                ln = it.line
                if ln.kind is LineKind.LABEL:
                    entry.label(ln, board)
                if ln.kind is not LineKind.INSTR:
                    continue
                op = (ln.opcode or "").lower()
                if cm.is_wait(op):
                    board.apply_wait(cm.parse_wait(op, ln.operands).targets)
                    continue
                if record:
                    for (r, c, s) in board.unmet_uses(ln, self.target):
                        violations.append(
                            "line {}: use of {} not synced ({} producer_seq={} > "
                            "done={})".format(ln.idx, r, c, s, board.done[c]))
                board.issue(ln, self.target)
                entry.instr(ln, board)

        # Walk once; each loop body gets a SECOND pass (seeded from the running
        # state, with previous-iteration producers live) and only that pass
        # records -- this exposes loop-carried under-synchronization.
        i, n = 0, len(items)
        while i < n:
            span = next(((sp, ep) for (sp, ep) in loop_spans if sp <= i <= ep), None)
            if span is None:
                walk([items[i]], record=True)
                i += 1
                continue
            sp, ep = span
            body = items[sp:ep + 1]
            walk(body, record=False)
            walk(body, record=True)
            i = ep + 1
        return violations

    # --- 2b. LDS round-trip + barrier-fence sufficiency (M5) --------------
    #
    # Two memory-ordering constraints invisible to register tracking:
    #   * LDS round-trip: a ``ds_read`` must wait (vmcnt) for the lds-direct
    #     loads that filled the buffer band it reads (slot-precise when the
    #     Target resolves the multi-buffer layout, else conservative).
    #   * barrier fence: every ``s_barrier`` must be preceded by lgkmcnt(0)
    #     (all ds_*/smem done) and a vmcnt draining all lds-direct loads, so
    #     other waves of the workgroup observe a consistent LDS.
    # Loop bodies get the same two-pass treatment as _waitcnt_sufficiency so
    # loop-carried (cross-iteration) LDS deps are exposed.
    def _lds_barrier_sufficiency(self, program) -> List[str]:
        cm = self.target.counter_model()
        counters = list(cm.names)
        if not hasattr(self.target, "lds_roundtrip_model"):
            return []
        items = regions._collect_code_items(program)
        instr = [it.line for it in items if it.line.kind is LineKind.INSTR]
        lds_model = self.target.lds_roundtrip_model(instr)

        loop_spans = []
        if self.analysis is not None:
            loop_spans = [(lp.header_pos, lp.tail_pos) for lp in self.analysis.loops
                          if 0 <= lp.header_pos <= lp.tail_pos < len(items)]

        from .model import Kind
        board = _Scoreboard(counters, lds_roundtrip=True, lds_model=lds_model, cm=cm)
        contract = board.contract is not None
        violations: List[str] = []

        def walk(seq_items, record):
            for it in seq_items:
                ln = it.line
                if ln.kind is not LineKind.INSTR:
                    continue
                op = (ln.opcode or "").lower()
                if cm.is_wait(op):
                    board.apply_wait(cm.parse_wait(op, ln.operands).targets)
                    continue
                if record:
                    kind = self.target.classify(op, ln.operands)
                    if contract or kind is Kind.DS_READ:
                        un = board.unmet_lds(ln, self.target)
                        if un is not None:
                            c, s = un
                            violations.append(
                                "line {}: {} LDS round-trip not synced "
                                "(lds-fill seq={} > {} done={})".format(
                                    ln.idx, op, s, c, board.done[c]))
                    if not contract and kind is Kind.BARRIER and \
                            is_barrier_release(self.target, op, ln.operands):
                        for (c, s) in board.unmet_barrier():
                            violations.append(
                                "line {}: barrier LDS-release fence missing on {} "
                                "(producer seq={} > done={})".format(
                                    ln.idx, c, s, board.done[c]))
                board.issue(ln, self.target)

        i, n = 0, len(items)
        while i < n:
            span = next(((sp, ep) for (sp, ep) in loop_spans if sp <= i <= ep), None)
            if span is None:
                walk([items[i]], record=True)
                i += 1
                continue
            sp, ep = span
            body = items[sp:ep + 1]
            first = contract and board._contract_first is not None
            board.first_iteration(first)
            walk(body, record=first)
            board.first_iteration(False)
            # rank-N requirements are only observable after N body instances
            for _ in range(getattr(lds_model, "depth", 1) - 2 if contract else 0):
                walk(body, record=False)
            walk(body, record=True)
            i = ep + 1
        return violations

    # --- 3. architecture invariants ---------------------------------------
    def _invariants(self, program) -> List[str]:
        out: List[str] = []
        for inv in self.target.invariants():
            out += inv.check(program, self.reference)
        return out
