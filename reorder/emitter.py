"""Emitter: Program -> assembly text (lossless).

M0 contract: emit() reconstructs the original source byte-for-byte by joining
each line's verbatim ``raw`` with '\\n'. Later milestones will render modified
instruction/waitcnt lines from structured fields; unmodified lines always fall
back to ``raw``.
"""
from __future__ import annotations

from .model import Program


def emit(program: Program) -> str:
    """Render a Program back to source text."""
    return "\n".join(line.raw for line in program.lines)


def write(program: Program, path: str, encoding: str = "utf-8") -> None:
    """Write a Program to a file (no newline translation)."""
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(emit(program))
