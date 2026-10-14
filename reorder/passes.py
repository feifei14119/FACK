"""FixupPass protocol + PassPipeline (architecture-agnostic).

After the pure reorder engine changes instruction ORDER, a per-architecture
ordered list of fixup passes patches the program so it is legal again --
recomputing synchronization, inserting forced nops, etc. There is no hardwired
NopFixer: each architecture supplies its passes via ``Target.fixup_pipeline()``.

A pass mutates ``program.lines`` in place and returns a reversible ``LineDiff``
(a snapshot of the line list before/after). ``PassPipeline.run`` executes the
target's passes in order and returns all diffs; ``revert`` restores the program.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, runtime_checkable

from .model import Line, Program


@dataclass
class LineDiff:
    """Reversible record of a line-level program edit."""

    pass_name: str
    before: List[Line]
    after: List[Line]
    note: str = ""

    @property
    def changed(self) -> bool:
        return self.before != self.after


@runtime_checkable
class FixupPass(Protocol):
    name: str

    def run(self, program: Program, target) -> LineDiff: ...


class PassPipeline:
    def __init__(self, passes: List[FixupPass]) -> None:
        self.passes = passes

    def run(self, program: Program, target) -> List[LineDiff]:
        diffs: List[LineDiff] = []
        for p in self.passes:
            diffs.append(p.run(program, target))
        return diffs

    @staticmethod
    def revert(program: Program, diffs: List[LineDiff]) -> None:
        """Undo a list of diffs (in reverse order)."""
        for d in reversed(diffs):
            program.lines = list(d.before)


def snapshot(program: Program) -> List[Line]:
    return list(program.lines)
