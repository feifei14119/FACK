"""gfx942 (CDNA3) Target package.

Importing this package registers the gfx942 Target in isa.registry.
"""
from __future__ import annotations

from .. import registry
from .target import Gfx942Target, _factory

registry.register("gfx942", _factory)

__all__ = ["Gfx942Target"]
