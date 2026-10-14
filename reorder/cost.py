"""Architecture-agnostic, GPU-less region cost model (M9 Phase 2).

A cheap static proxy for a region's execution cost, used by the search/agent
layer as (a) a pre-filter before paying for a real-HW run and (b) a tie-breaker
when a candidate's measured TFLOPS delta falls inside the baseline noise band
(see proj/anchorless_region_scheduling.md §3). It is NEVER the verdict: real-HW
TFLOPS + correctness always decide, and the cost model can never overturn a
measured regression.

It reuses the same scoreboard walk as ``waitcnt.simulate`` but scoped to one
region and turned into a scalar cost. Counters are seeded empty at the region
start (a local proxy); for comparing two ORDERINGS of the SAME region that seed
bias cancels, which is exactly the use case.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from . import regions
from .model import COUNTER_OF, Kind

# Rough per-kind issue cost (cycles). Architecture-agnostic proxy weights; MFMA
# occupies the issue port longer, plain ALU/mem issue in ~1 slot.
_ISSUE_COST = {
    Kind.MFMA: 4,
    Kind.WAITCNT: 0,   # waits are costed via their drain depth, not issue
}
_DEFAULT_ISSUE = 1

# Each wait instruction has a synchronization overhead and forecloses overlap;
# batching one wait over N async ops is preferable to N separate waits.
_WAIT_PENALTY = 2

_WAITTYPE_TO_COUNTER = COUNTER_OF


@dataclass
class RegionCost:
    issue_cycles: int       # Σ per-kind issue cost of the region's instructions
    wait_stalls: int        # Σ drained outstanding async ops over all waits
    n_waits: int            # number of s_waitcnt in the region
    est_cycles: int         # issue + wait_stalls + wait penalty (primary key)

    def to_dict(self) -> Dict[str, int]:
        return {"issue_cycles": self.issue_cycles, "wait_stalls": self.wait_stalls,
                "n_waits": self.n_waits, "est_cycles": self.est_cycles}


def estimate(program, target, region) -> RegionCost:
    """Static cost of one region in its CURRENT program order.

    Walk the region's instruction lines, accumulating per-counter outstanding
    async ops (drained at each wait), and turn it into a scalar ``est_cycles``.
    Intended for relative comparison between orderings of the same region; it is
    a proxy, not a cycle-accurate model."""
    return estimate_lines(regions.region_instr_lines(program, region), target)


def estimate_lines(instr_lines, target) -> RegionCost:
    """Same scoreboard-walk cost, but over an explicit ORDERED list of instruction
    ``Line`` objects (a whole region, or a fence-bounded segment of one). Lets the
    agent layer cost an arbitrary sub-sequence -- e.g. per fence-segment est_cycles
    for large anchor-less regions (proj/brainstorm/large_dag_finetune.md dir. 2)."""
    cm = target.counter_model()
    counters = list(cm.names)
    outstanding: Dict[str, int] = {c: 0 for c in counters}
    issue = wait_stalls = n_waits = 0

    for ln in instr_lines:
        op = (ln.opcode or "").lower()
        if not op:
            continue
        if cm.is_wait(op):
            spec = cm.parse_wait(op, ln.operands)
            for c in counters:
                tgt = spec.targets.get(c)
                if tgt is None:
                    continue
                if outstanding[c] > tgt:
                    wait_stalls += outstanding[c] - tgt
                    outstanding[c] = tgt
            n_waits += 1
            continue
        kind = target.classify(op, ln.operands)
        issue += _ISSUE_COST.get(kind, _DEFAULT_ISSUE)
        counter = _WAITTYPE_TO_COUNTER.get(target.wait_type(op, ln.operands))
        if counter is not None:
            outstanding[counter] += 1

    est = issue + wait_stalls + _WAIT_PENALTY * n_waits
    return RegionCost(issue, wait_stalls, n_waits, est)
