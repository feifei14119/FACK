"""Core data model for the architecture-agnostic reorder engine.

M0 scope: only the *line* model needed for lossless parse/emit is exercised.
The semantic enums (Kind / WaitType / EdgeType) are declared here for forward
use by later milestones (M1+: filled in by the isa/Target layer); M0 does not
populate them.

Target: Python 3.8+ (uses dataclasses + __future__ annotations).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class LineKind(Enum):
    """Lexical classification of a source line (used by parser/emitter)."""

    BLANK = "blank"          # empty or whitespace-only
    COMMENT = "comment"      # whole-line comment
    DIRECTIVE = "directive"  # .text / .amdhsa_* / .set / .p2align / ...
    LABEL = "label"          # label_XXXX:  or  .label_exit:
    INSTR = "instr"          # an instruction line
    OTHER = "other"          # anything not confidently classified (e.g. YAML metadata)


class Kind(Enum):
    """Semantic category of an instruction. Assigned by isa/Target in M1+."""

    MFMA = "mfma"
    VMEM_LOAD = "vmem_load"
    VMEM_STORE = "vmem_store"
    DS_READ = "ds_read"
    DS_WRITE = "ds_write"
    SMEM = "smem"
    VALU = "valu"
    SALU = "salu"
    SET_M0 = "set_m0"
    WAITCNT = "waitcnt"
    BARRIER = "barrier"
    NOP = "nop"
    BRANCH = "branch"
    OTHER = "other"
    UNKNOWN = "unknown"


class WaitType(Enum):
    """Which hardware counter an instruction increments.

    The concrete set / widths / increment rules are provided by an
    isa/<arch> CounterModel (M1+). VM/LGKM/EXP/VS cover the gfx942 / CDNA family;
    LOAD..TENSOR are optional split counters for future Target implementations.
    """

    VM = "vmcnt"        # VMEM load + atomic-return
    LGKM = "lgkmcnt"    # LDS (ds_*) + SMEM (s_load) + s_sendmsg
    EXP = "expcnt"
    VS = "vscnt"        # VMEM store (separate from vmcnt) -- gfx942 necessity
    LOAD = "loadcnt"    # optional vector load / atomic-return counter
    STORE = "storecnt"  # optional vector store / atomic-without-return counter
    DS = "dscnt"        # optional LDS counter
    KM = "kmcnt"        # optional out-of-order SMEM / message counter
    ASYNC = "asynccnt"  # optional global<->LDS async copies
    TENSOR = "tensorcnt"  # optional tensor transfers
    NONE = "none"


#: WaitType -> CounterModel counter name (shared by waitcnt / cost / session).
COUNTER_OF = {
    WaitType.VM: "vm",
    WaitType.LGKM: "lgkm",
    WaitType.EXP: "exp",
    WaitType.VS: "vs",
    WaitType.LOAD: "load",
    WaitType.STORE: "store",
    WaitType.DS: "ds",
    WaitType.KM: "km",
    WaitType.ASYNC: "async",
    WaitType.TENSOR: "tensor",
}


class EdgeType(Enum):
    """Dependency edge kinds in the (M2) dependency graph."""

    RAW = "raw"
    WAR = "war"
    WAW = "waw"
    MEM = "mem"
    M0 = "m0"
    ACC = "acc_chain"
    FENCE = "fence"


@dataclass
class Line:
    """One source line, classified, with structured fields parsed best-effort.

    Invariant for losslessness: ``raw`` holds the EXACT original line content
    with the newline delimiter removed (the program is re-joined with '\\n').
    The structured fields below are derived views and are NOT used to emit in
    M0 -- the emitter writes ``raw`` verbatim.
    """

    idx: int                                  # 0-based position in the file
    raw: str                                  # exact original text (no trailing '\n')
    kind: LineKind

    indent: str = ""                          # leading whitespace of the line body
    label: Optional[str] = None               # label name (LABEL lines), without ':'
    opcode: Optional[str] = None              # mnemonic (INSTR lines)
    operands: List[str] = field(default_factory=list)  # comma-split operand fields
    directive: Optional[str] = None           # directive name incl leading '.' (DIRECTIVE)
    comment: Optional[str] = None             # trailing/whole-line comment text incl marker

    # Semantic fields (assigned in M1+ by Target.classify); unused in M0.
    sem: Kind = Kind.UNKNOWN
    # Target-private semantic annotations; never emitted.
    meta: Dict = field(default_factory=dict)

    @property
    def is_instr(self) -> bool:
        return self.kind is LineKind.INSTR

    @property
    def is_label(self) -> bool:
        return self.kind is LineKind.LABEL


@dataclass
class Program:
    """A parsed assembly file as an ordered list of classified lines.

    ``'\\n'.join(line.raw for line in lines)`` reconstructs the original file
    byte-for-byte (see emitter.emit).
    """

    lines: List[Line] = field(default_factory=list)

    def instr_lines(self) -> List[Line]:
        return [ln for ln in self.lines if ln.kind is LineKind.INSTR]

    def label_lines(self) -> List[Line]:
        return [ln for ln in self.lines if ln.kind is LineKind.LABEL]

    def count(self, kind: LineKind) -> int:
        return sum(1 for ln in self.lines if ln.kind is kind)
