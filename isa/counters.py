"""Architecture-agnostic hardware counter model interface.

A CounterModel describes the set of asynchronous hardware counters an ISA
exposes (their names, bit widths, which instruction increments which counter)
and knows how to parse / format that ISA's wait instructions.

The reorder core (waitcnt simulation, scheduler) talks to this interface only;
the concrete gfx942 model lives in isa/gfx942/counters.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class WaitSpec:
    """A parsed wait instruction: target counter values (None = no constraint).

    Keys are counter names (e.g. 'vm', 'lgkm', 'exp', 'vs'). A value N means
    'wait until at most N outstanding'; None means this counter is unconstrained.
    """

    targets: Dict[str, Optional[int]] = field(default_factory=dict)

    def constrains(self, name: str) -> bool:
        return self.targets.get(name) is not None


class CounterModel:
    """Base class; subclass per architecture."""

    #: ordered counter names
    names: List[str] = []
    #: max value (width) per counter name
    widths: Dict[str, int] = {}

    # --- architecture hooks consumed by reorder/waitcnt (defaults = gfx942) ---
    #: counters drained FULLY before a workgroup barrier (LDS-release fence)
    barrier_drain_counters: Tuple[str, ...] = ("lgkm",)
    #: counter shared by out-of-order scalar-memory returns (only a 0 wait proves
    #: any SMEM result is back); None = no out-of-order counter
    smem_counter: Optional[str] = "lgkm"
    #: counter that must drain the outstanding LDS *reads* before an LDS-fill op
    #: (async/TDM global->LDS) may overwrite LDS (WAR); None = not required
    lds_fill_war_counter: Optional[str] = None
    #: counters whose events are latency-hiding memory ops (agent tunables)
    latency_counters: Tuple[str, ...] = ("vm", "lgkm")
    #: also sync register WAW against in-flight async writes of another counter
    waw_sync: bool = False
    #: loop recompute starts from the pre-loop scoreboard (ops issued before
    #: the loop may still be in flight inside it) instead of an empty one
    seed_loop_entry: bool = False

    def width(self, name: str) -> int:
        return self.widths[name]

    def format_waits(self, targets: Dict[str, int]) -> List[Tuple[str, List[str], str]]:
        """Encode recomputed ``{counter: n}`` targets as wait instructions.

        Returns ``[(opcode, operands, body_text)]`` in emission order."""
        raise NotImplementedError

    # --- wait instruction parsing / formatting (override per arch) ---------
    def is_wait(self, opcode: str) -> bool:
        raise NotImplementedError

    def parse_wait(self, opcode: str, operands: List[str]) -> WaitSpec:
        raise NotImplementedError

    def format_wait(self, spec: WaitSpec) -> str:
        raise NotImplementedError
