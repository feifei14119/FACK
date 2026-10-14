"""gfx942 ATT instruction-category schema (see proj/amdgpu-dump-parsing.md §6).

Maps the ATT ``Inst.category`` (``_catstall & 0xFF``) to a human name and a
coarse bottleneck *dimension* that analysis/bottleneck.py reasons about. MFMA /
WMMA are folded into VALU by the SDK; splitting them needs disassembly text.
"""
from __future__ import annotations

# category int -> {"name", "dimension"}
GFX942_ATT_SCHEMA = {
    0:  {"name": "NONE",    "dimension": "none"},
    1:  {"name": "SMEM",    "dimension": "scalar_mem"},
    2:  {"name": "SALU",    "dimension": "scalar"},
    3:  {"name": "VMEM",    "dimension": "memory"},
    4:  {"name": "FLAT",    "dimension": "memory"},
    5:  {"name": "LDS",     "dimension": "lds"},
    6:  {"name": "VALU",    "dimension": "compute"},   # incl. MFMA/WMMA
    7:  {"name": "JUMP",    "dimension": "flow"},
    8:  {"name": "NEXT",    "dimension": "none"},
    9:  {"name": "IMMED",   "dimension": "none"},
    10: {"name": "CONTEXT", "dimension": "none"},
    11: {"name": "MESSAGE", "dimension": "none"},
    12: {"name": "BVH",     "dimension": "compute"},
}
