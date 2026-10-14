"""testft reorder engine -- architecture-agnostic core.

M0 surface: parse / emit (lossless round-trip) and the line/instruction model.
Later milestones add regions, depgraph, editor, waitcnt, passes, verifier.
"""
from __future__ import annotations

from .emitter import emit, write
from .model import EdgeType, Kind, Line, LineKind, Program, WaitType
from .parser import parse, parse_file

__all__ = [
    "parse",
    "parse_file",
    "emit",
    "write",
    "Program",
    "Line",
    "LineKind",
    "Kind",
    "WaitType",
    "EdgeType",
]
