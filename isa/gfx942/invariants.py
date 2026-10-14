"""gfx942 architecture invariants (checked by reorder.verifier).

Each invariant exposes ``name`` and ``check(program, reference) -> list[str]``
(empty list = satisfied).
"""
from __future__ import annotations

from typing import List, Optional

from reorder.model import LineKind, Program


def _count_opcode(program: Optional[Program], prefix: str) -> int:
    if program is None:
        return -1
    return sum(1 for ln in program.lines
               if ln.kind is LineKind.INSTR and (ln.opcode or "").lower().startswith(prefix))


class BarrierCountLocked:
    """``s_barrier`` is collective: passes/reorder must not change how many
    barriers each wave executes. Compares against the reference program."""

    name = "barrier_count_locked"

    def check(self, program: Program, reference: Optional[Program]) -> List[str]:
        if reference is None:
            return []
        got = _count_opcode(program, "s_barrier")
        want = _count_opcode(reference, "s_barrier")
        if got != want:
            return ["barrier count changed: {} -> {}".format(want, got)]
        return []


class WaitcntEncodable:
    """Every emitted wait target must fit its counter field width."""

    name = "waitcnt_encodable"

    def __init__(self, counter_model):
        self.cm = counter_model

    def check(self, program: Program, reference: Optional[Program]) -> List[str]:
        out: List[str] = []
        for ln in program.lines:
            if ln.kind is not LineKind.INSTR:
                continue
            op = (ln.opcode or "").lower()
            if not self.cm.is_wait(op):
                continue
            spec = self.cm.parse_wait(op, ln.operands)
            for c, v in spec.targets.items():
                if v is not None and v > self.cm.width(c):
                    out.append("line {}: {} target {} > width {}".format(
                        ln.idx, c, v, self.cm.width(c)))
        return out
