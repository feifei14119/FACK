"""gfx942 operand / register model: operand strings -> RegSet.

Handles the register syntaxes actually seen in gfx942 asm:
  - scalar   sN / s[lo:hi]
  - vector   vN / v[lo:hi]
  - accum    aN / a[lo:hi]   AND  accN / acc[lo:hi]  (both are AGPRs)
  - special  m0 / vcc(_lo/_hi) / exec(_lo/_hi) / scc / null / off
  - immediates (0x.., decimal, negative) -> no register units
  - .set aliases (optional map): s[s_karg:s_karg+1] etc.

Reference: amdgpu-asm-codebase/llvm-isa/gfx942/02-notation-operands-modifiers.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# A register unit is either ('s'|'v'|'a', index) or a special name string.
Unit = object  # Tuple[str, int] | str

# Operand-position modifier tokens that are NOT registers/immediates.
MODIFIER_TOKENS = {
    "offen", "idxen", "off", "lds", "glc", "slc", "dlc",
    "sc0", "sc1", "nt", "gds",
}

_RANGE_RE = re.compile(r"^(s|v|a|acc)\[([^\]]+)\]$")
_SINGLE_RE = re.compile(r"^(s|v|a|acc)(\d+)$")
_OFFSET_RE = re.compile(r"^[A-Za-z_.$][\w$.]*$")


def _norm_class(prefix: str) -> str:
    """Map an operand prefix to a canonical register class char."""
    return "a" if prefix in ("a", "acc") else prefix


@dataclass
class RegSet:
    """A normalized set of register units, e.g. {('v',36),('v',37),'m0'}."""

    units: Set[Unit] = field(default_factory=set)

    def overlaps(self, other: "RegSet") -> bool:
        return bool(self.units & other.units)

    def __bool__(self) -> bool:
        return bool(self.units)

    def __or__(self, other: "RegSet") -> "RegSet":
        return RegSet(self.units | other.units)


def _eval_index(expr: str, aliases: Optional[Dict[str, int]]) -> Optional[int]:
    """Evaluate a register index expression: int literal or alias[(+|-)int]."""
    expr = expr.strip()
    if not expr:
        return None
    # plain integer
    try:
        return int(expr, 0)
    except ValueError:
        pass
    # alias [+/- offset]
    m = re.match(r"^([A-Za-z_.$][\w$.]*)\s*([+-]\s*\d+)?$", expr)
    if m and aliases is not None:
        base = aliases.get(m.group(1))
        if base is None:
            return None
        off = 0
        if m.group(2):
            off = int(m.group(2).replace(" ", ""))
        return base + off
    return None


def _expand_range(cls: str, lo: int, hi: int) -> Set[Unit]:
    if hi < lo:
        lo, hi = hi, lo
    return {(cls, i) for i in range(lo, hi + 1)}


_SPECIAL = {
    "vcc": "vcc", "vcc_lo": "vcc", "vcc_hi": "vcc",
    "exec": "exec", "exec_lo": "exec", "exec_hi": "exec",
    "scc": "scc",
    "m0": "m0",
}
_NO_UNIT = {"null", "off"}


def parse_token(tok: str, aliases: Optional[Dict[str, int]] = None) -> Set[Unit]:
    """Parse a single operand token into register units (may be empty)."""
    tok = tok.strip()
    if not tok:
        return set()

    low = tok.lower()
    if low in _SPECIAL:
        return {_SPECIAL[low]}
    if low in _NO_UNIT or low in MODIFIER_TOKENS:
        return set()

    m = _RANGE_RE.match(tok)
    if m:
        cls = _norm_class(m.group(1))
        inner = m.group(2)
        if ":" in inner:
            a, b = inner.split(":", 1)
            lo = _eval_index(a, aliases)
            hi = _eval_index(b, aliases)
        else:
            lo = hi = _eval_index(inner, aliases)
        if lo is None or hi is None:
            return set()
        return _expand_range(cls, lo, hi)

    m = _SINGLE_RE.match(tok)
    if m:
        return {(_norm_class(m.group(1)), int(m.group(2)))}

    # immediates / labels / unknown -> no register units
    return set()


def is_lds_modifier(operands: List[str]) -> bool:
    """True if any operand field carries the ``lds`` modifier (buffer_load ... lds)."""
    for f in operands:
        for tok in f.split():
            if tok == "lds":
                return True
    return False


def parse_operand_field(field_str: str, aliases: Optional[Dict[str, int]] = None) -> Set[Unit]:
    """Parse one comma-separated operand field. Only the leading token can be a
    register/immediate; the rest are space-separated modifiers."""
    field_str = field_str.strip()
    if not field_str:
        return set()
    first = field_str.split()[0]
    return parse_token(first, aliases)


def collect_aliases(set_directives: List[Tuple[str, str]]) -> Dict[str, int]:
    """Build an alias map from parsed ``.set name, value`` pairs (best-effort)."""
    aliases: Dict[str, int] = {}
    for name, value in set_directives:
        tok = value.strip().split()[0] if value and value.strip() else ""
        try:
            aliases[name] = int(tok, 0)
        except (ValueError, TypeError):
            continue
    return aliases
