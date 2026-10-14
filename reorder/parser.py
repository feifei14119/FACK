"""Parser: assembly text -> Program (a list of classified Lines).

Lossless by construction: the file content is split on '\\n' and each part is
kept verbatim in ``Line.raw``. Re-joining with '\\n' reproduces the input
byte-for-byte (see emitter.emit). Splitting on '\\n' (rather than
str.splitlines, which also breaks on \\x0b/\\x0c/\\u2028/... ) guarantees
split/join is an exact inverse, including CRLF endings and a missing final
newline.
"""
from __future__ import annotations

from typing import List

from . import lexer
from .model import Line, LineKind, Program

# Directive blocks whose body is free-form text (YAML metadata) and must NOT be
# lexically classified as labels/instructions. Mapping: open-directive -> close.
_PASSTHROUGH_BLOCKS = {
    ".amdgpu_metadata": ".end_amdgpu_metadata",
}


def parse(text: str) -> Program:
    """Parse assembly source text into a Program.

    Lines inside a passthrough block (e.g. ``.amdgpu_metadata`` ...
    ``.end_amdgpu_metadata``) are forced to OTHER so YAML lines such as
    ``amdhsa.kernels:`` are not mistaken for labels. The open/close directives
    themselves keep their DIRECTIVE classification. Losslessness is unaffected
    (``raw`` is always preserved verbatim).
    """
    parts = text.split("\n")
    lines: List[Line] = []
    close_token = None  # set while inside a passthrough block
    for idx, raw in enumerate(parts):
        info = lexer.classify(raw)
        directive = info.get("directive")

        if close_token is not None:
            if directive == close_token:
                close_token = None  # this line is the closing directive (kept)
            else:
                info = {"kind": LineKind.OTHER, "indent": info.get("indent", ""),
                        "comment": info.get("comment")}
        elif directive in _PASSTHROUGH_BLOCKS:
            close_token = _PASSTHROUGH_BLOCKS[directive]

        lines.append(Line(idx=idx, raw=raw, **info))
    return Program(lines=lines)


def parse_file(path: str, encoding: str = "utf-8") -> Program:
    """Read and parse an assembly file."""
    with open(path, "r", encoding=encoding, newline="") as f:
        text = f.read()
    return parse(text)
