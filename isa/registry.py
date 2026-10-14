"""Target registry: select an architecture implementation by name.

Usage:  target = isa.registry.get("gfx942")
        target = isa.registry.target_for_program(prog)   # arch from .amdgcn_target

Adding an architecture is a one-line registration plus its isa/<arch>/ package
(registered: gfx942).
"""
from __future__ import annotations

import re
from typing import Callable, Dict, Optional

# name -> factory returning a Target instance
_REGISTRY: Dict[str, Callable[[], object]] = {}


def register(name: str, factory: Callable[[], object]) -> None:
    _REGISTRY[name] = factory


def available() -> list:
    return sorted(_REGISTRY.keys())


def get(name: str) -> object:
    if name not in _REGISTRY:
        # lazy-load the isa/<name>/ package, which self-registers on import
        try:
            import importlib

            importlib.import_module("isa.{}".format(name))
        except ImportError:
            pass
    if name not in _REGISTRY:
        raise KeyError(
            "no Target registered for {!r}; available: {}.".format(name, available())
        )
    return _REGISTRY[name]()


DEFAULT_ARCH = "gfx942"

# .amdgcn_target "amdgcn-amd-amdhsa--gfx942:sramecc+:xnack-"  -> gfx942
_ARCH_RE = re.compile(r"\b(gfx[0-9a-f]+)\b")


def arch_of_program(program, default: str = DEFAULT_ARCH) -> str:
    """The gfx architecture a parsed program targets, from ``.amdgcn_target``
    (falls back to ``default`` when the directive is absent)."""
    for ln in program.lines:
        if ln.directive == ".amdgcn_target":
            m = _ARCH_RE.search(ln.raw)
            if m:
                return m.group(1)
    return default


def arch_of_source(text: str, default: str = DEFAULT_ARCH) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(".amdgcn_target"):
            m = _ARCH_RE.search(s)
            if m:
                return m.group(1)
    return default


def target_class(name: str):
    """The registered Target class for ``name`` (for ``from_program``)."""
    return type(get(name))


def target_for_program(program, arch: Optional[str] = None):
    """Build the Target for ``program`` (arch from ``.amdgcn_target`` unless
    given). Targets may normalise the program in place."""
    return target_class(arch or arch_of_program(program)).from_program(program)


def target_for_source(text: str):
    """A program-less Target for the arch named in ``text`` (enough for the
    evaluator: kernel symbols, perf schema)."""
    return get(arch_of_source(text))
