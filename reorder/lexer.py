"""Line-level lexer for AMDGPU GAS-style assembly.

Architecture-agnostic on purpose: it only does *lexical* classification
(blank / comment / directive / label / instruction) and a best-effort split
into opcode + operand fields + trailing comment. It does NOT understand any
specific opcode or register -- that semantic step belongs to the isa/Target
layer (M1+).

Reference: amdgpu-asm-codebase/gun-asm/GNU_Assembler_GAS_Standard.md and
amdgpu-asm-codebase/llvm-isa/gfx942/02-notation-operands-modifiers.md
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .model import LineKind

# Whole-line / trailing comment markers seen in practice:
#   ';'  -> ISA docs / many AMD asm
#   '//' -> e.g. test/k_vadd.s
# '#' is intentionally NOT treated as a comment marker by default: it is too
# ambiguous (appears in metadata/text); losslessness does not depend on it.
_COMMENT_MARKERS = ("//", ";")

# A label is: optional leading whitespace, an identifier (GAS allows '.', '_',
# '$', letters, digits; must not start with a digit), then ':'. The remainder
# must be empty or a comment.
_LABEL_RE = re.compile(r"^[ \t]*([A-Za-z_.$][\w$.]*)[ \t]*:[ \t]*$")

# An instruction mnemonic starts with a lowercase letter (AMDGPU mnemonics are
# lowercase: v_*, s_*, ds_*, buffer_*, global_*, flat_*, scratch_*).
_INSTR_RE = re.compile(r"^[ \t]*([a-z][A-Za-z0-9_]*)\b")

_INDENT_RE = re.compile(r"^[ \t]*")


def _strip_cr(raw: str) -> str:
    """Drop a single trailing CR so CRLF files classify correctly.

    The original ``raw`` (with the CR) is what gets emitted; this is only for
    classification.
    """
    return raw[:-1] if raw.endswith("\r") else raw


def find_comment(body: str) -> int:
    """Return the index of the first top-level comment marker, or -1.

    "Top-level" means not inside ``[]`` or ``()`` brackets (so an operand like
    ``s[8:11]`` never confuses things). Bracket depth is tracked conservatively.
    """
    depth = 0
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c in "[(":
            depth += 1
        elif c in "])":
            if depth > 0:
                depth -= 1
        elif depth == 0:
            for mk in _COMMENT_MARKERS:
                if body.startswith(mk, i):
                    return i
        i += 1
    return -1


def split_operands(operand_str: str) -> List[str]:
    """Split an operand region on top-level commas (ignoring commas in []/()).

    Each field is stripped of surrounding whitespace. Trailing modifiers that
    are space-separated (e.g. ``0 offen lds``) stay attached to their field;
    structured modifier parsing is the Target layer's job (M1+).
    """
    fields: List[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(operand_str):
        if c in "[(":
            depth += 1
        elif c in "])":
            if depth > 0:
                depth -= 1
        elif c == "," and depth == 0:
            fields.append(operand_str[start:i].strip())
            start = i + 1
    tail = operand_str[start:].strip()
    if tail or fields:  # keep a trailing field; avoid spurious [''] for no operands
        fields.append(tail)
    return [f for f in fields] if fields else []


def classify(raw: str) -> dict:
    """Classify one raw line (newline already removed) into structured fields.

    Returns a dict suitable for constructing a model.Line (minus idx/raw).
    Never raises; unknown lines fall back to OTHER/DIRECTIVE.
    """
    body = _strip_cr(raw)
    indent = _INDENT_RE.match(body).group(0)
    stripped = body.strip()

    # Blank
    if stripped == "":
        return {"kind": LineKind.BLANK, "indent": indent}

    # Whole-line comment
    for mk in _COMMENT_MARKERS:
        if stripped.startswith(mk):
            return {"kind": LineKind.COMMENT, "indent": indent, "comment": stripped}

    # Label (must check before directive: ".label_exit:" is a label, not a directive)
    m = _LABEL_RE.match(body)
    if m:
        return {"kind": LineKind.LABEL, "indent": indent, "label": m.group(1)}

    # Split off any trailing comment for the remaining cases
    cpos = find_comment(body)
    if cpos >= 0:
        code = body[:cpos].rstrip()
        comment = body[cpos:]
    else:
        code = body.rstrip()
        comment = None
    code_stripped = code.strip()

    # Directive (starts with '.', and is not a label)
    if code_stripped.startswith("."):
        directive = code_stripped.split()[0] if code_stripped.split() else code_stripped
        return {
            "kind": LineKind.DIRECTIVE,
            "indent": indent,
            "directive": directive,
            "comment": comment,
        }

    # Instruction (mnemonic starts lowercase)
    mi = _INSTR_RE.match(code)
    if mi:
        opcode = mi.group(1)
        rest = code[mi.end():].strip()
        operands = split_operands(rest) if rest else []
        return {
            "kind": LineKind.INSTR,
            "indent": indent,
            "opcode": opcode,
            "operands": operands,
            "comment": comment,
        }

    # Anything else (e.g. YAML metadata lines: '---', 'amdhsa.kernels:', '- .name:')
    return {"kind": LineKind.OTHER, "indent": indent, "comment": comment}
