"""ISA abstraction layer (architecture-pluggable).

Exposes the Target contract and a name-based registry. Concrete targets live
in isa/<arch>/ subpackages (first: isa/gfx942, landing in M1).
"""
from __future__ import annotations

from . import registry
from .target import Target

__all__ = ["Target", "registry"]
