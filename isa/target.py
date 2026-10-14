"""ISA abstraction layer: the Target contract.

The architecture-agnostic core (reorder/*) consumes ONLY this interface; it
never references gfx942 directly. Adding a new architecture means adding a new
``isa/<arch>/`` package that implements Target -- the core does not change.

M0 status: the contract is declared (Protocol). The first concrete
implementation (gfx942) and the CounterModel land in M1.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, Set, Tuple, runtime_checkable

if TYPE_CHECKING:  # avoid hard import cycles; these are only type hints
    from reorder.model import Kind, Line


@runtime_checkable
class Target(Protocol):
    """Per-architecture knowledge consumed by the core engine.

    Method groups:
      - lexing/operands: register prefixes + operand -> (defs, uses)
      - classification:  opcode/operands -> semantic Kind
      - control flow:    branch detection + branch target resolution
      - dependencies:    architecture-specific edges + movable bundles
      - counters/fixups: CounterModel + ordered FixupPass pipeline
      - analysis:        perf-counter field semantics
      - invariants:      architecture safety checks (e.g. barrier count-lock)
    """

    name: str

    # --- lexing / operands -------------------------------------------------
    def register_prefixes(self) -> Set[str]: ...

    def parse_operands(self, opcode: str, operand_strs: List[str]) -> Tuple["object", "object"]:
        """Return (defs, uses) as RegSet-like objects."""
        ...

    # --- classification ----------------------------------------------------
    def classify(self, opcode: str, operands: List[str]) -> "Kind": ...

    # --- control flow ------------------------------------------------------
    def is_branch(self, line: "Line") -> bool: ...

    def is_conditional_branch(self, line: "Line") -> bool: ...

    def branch_target(self, line: "Line") -> Optional[str]: ...

    # --- dependencies ------------------------------------------------------
    def build_edges(self, region: "object", graph: "object") -> None: ...

    def bundles(self, region: "object") -> List["object"]: ...

    # --- counters / fixups -------------------------------------------------
    def counter_model(self) -> Optional["object"]: ...

    def fixup_pipeline(self) -> List["object"]: ...

    # --- analysis ----------------------------------------------------------
    def perf_counter_schema(self) -> Dict[str, "object"]: ...

    # --- invariants --------------------------------------------------------
    def invariants(self) -> List["object"]: ...
