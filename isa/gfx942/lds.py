"""gfx942 LDS round-trip slot/buffer resolver (M5).

The single correctness gap left by M4 was the LDS round-trip dependency:

    s_add_u32   m0, IMM, sBASE        ; m0 = LDS write address
    buffer_load v30, s[4:7], 0 ... lds ; writes LDS at m0    (counts vmcnt)
    ...
    ds_read_b128 acc[..], v34 offset:N ; reads LDS at v34+N  (counts lgkmcnt)

The store is a VMEM load whose *destination is LDS* (vmcnt), the consumer is a
``ds_read`` (lgkmcnt). The dependency flows through LDS memory and is therefore
invisible to register-scoreboard tracking. M4 guarded it with a single
conservative "newest outstanding lds-load" bucket which (a) had an operand-match
bug making it a no-op and (b) even when fixed binds a ds_read to a *same-group*
lds-load that fills a DIFFERENT buffer -> wrong target / over-synchronization.

This module recovers the multi-buffer (ping-pong / triple-buffer) structure
statically so each ds_read binds to the lds-loads that actually fill the buffer
it reads:

  * lds-loads select their buffer via the m0 base register; the base registers
    form a constant add-chain off a common LDS root (e.g.
    ``s58 = root+0 ; s59 = root+0x1080 ; s60 = root+0x2100``).  Constant-folding
    that chain yields each load's absolute LDS write offset.
  * ds_reads select their buffer via ``v34 + offset:N``; the read base ``v34`` is
    a single (per-lane) root, so ``N`` alone selects the buffer *band*.
  * both sides share the same buffer stride (the add-chain delta == the read
    offset band size), so ``offset // stride`` (reads) and
    ``(base_const + imm) // stride`` (writes) yield matching buffer indices.

A ds_read of buffer ``k`` then depends only on lds-loads of buffer ``k``; the
recompute waits for the newest such load (older same-buffer loads complete by
FIFO), which is always from an earlier pipeline stage -- never the same-group
loads that fill a different band. When the structure cannot be resolved
(unexpected addressing), ``resolved`` is False and the caller falls back to the
conservative single-bucket behaviour (always correct, possibly over-tight).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from typing import Dict, List, Optional, Tuple

from reorder.model import Kind, LineKind


# A symbolic scalar value: (root_register_or_None, const). root None == pure
# integer constant; a non-None root means "unknown base + const".
SymVal = Tuple[Optional[str], int]


@dataclass
class LdsModel:
    """Resolved per-line LDS buffer assignment for one linear instr stream."""

    write_idx: Dict[int, int] = field(default_factory=dict)   # lds-load line.idx -> buffer
    read_idx: Dict[int, int] = field(default_factory=dict)    # ds_read line.idx -> buffer
    stride: int = 0
    n_buffers: int = 0
    resolved: bool = False

    def write_buffer(self, line_idx: int) -> Optional[int]:
        return self.write_idx.get(line_idx)

    def read_buffer(self, line_idx: int) -> Optional[int]:
        return self.read_idx.get(line_idx)


def _imm(tok: str) -> Optional[int]:
    tok = tok.strip().split()[0] if tok.strip() else ""
    try:
        return int(tok, 0)
    except ValueError:
        return None


def _val(tok: str, sval: Dict[str, SymVal]) -> SymVal:
    """Symbolic value of an operand token: pure const, known reg, or own root."""
    tok = tok.strip().split()[0] if tok.strip() else ""
    iv = _imm(tok)
    if iv is not None:
        return (None, iv)
    return sval.get(tok, (tok, 0))


def _add(x: SymVal, y: SymVal, sign: int = 1) -> Optional[SymVal]:
    rx, cx = x
    ry, cy = y
    cy *= sign
    if ry is None:
        return (rx, cx + cy)
    if rx is None and sign == 1:
        return (ry, cx + cy)
    return None  # two unknown roots (or subtracting a root) -> unfoldable


def _read_offset(operands: List[str]) -> int:
    for f in operands:
        for tok in f.split():
            if tok.startswith("offset:"):
                v = _imm(tok.split(":", 1)[1])
                return v or 0
    return 0


def build_lds_model(instr_lines: List, target, scope_idxs=None) -> LdsModel:
    """Resolve LDS buffer indices for every lds-load / ds_read in scope.

    A single forward pass constant-folds scalar add-chains to learn each m0 base
    register's LDS offset, then assigns buffer indices by ``offset // stride``.

    ``instr_lines`` should span from (at least) the point the LDS base chain is
    established -- typically the whole ``.text`` stream -- so the
    prologue-defined base registers fold to constants. ``scope_idxs`` (a set of
    ``line.idx``) limits which lds-loads/ds_reads are *recorded*; when None all
    are recorded. Folding always runs over the full ``instr_lines``.
    """
    sval: Dict[str, SymVal] = {}
    # per lds-load: (line_idx, base_register_symval, intra-buffer imm)
    writes: List[Tuple[int, Optional[SymVal], int]] = []
    reads: List[Tuple[int, int]] = []
    m0_base: Optional[SymVal] = None    # m0's base-register part (selects buffer)
    m0_imm: int = 0                     # m0's immediate part (intra-buffer slot)

    for ln in instr_lines:
        if ln.kind is not LineKind.INSTR or not ln.opcode:
            continue
        op = ln.opcode.lower()
        ops = ln.operands

        # --- constant-fold scalar moves / adds (build the LDS base chain) ---
        if ops:
            dst = ops[0].strip().split()[0] if ops[0].strip() else ""
            if op in ("s_mov_b32", "s_mov_b64") and len(ops) >= 2:
                sval[dst] = _val(ops[1], sval)
            elif op in ("s_add_u32", "s_add_i32", "s_addk_i32") and len(ops) >= 3:
                r = _add(_val(ops[1], sval), _val(ops[2], sval))
                sval[dst] = r if r is not None else (dst, 0)
            elif op in ("s_sub_u32", "s_sub_i32") and len(ops) >= 3:
                r = _add(_val(ops[1], sval), _val(ops[2], sval), sign=-1)
                sval[dst] = r if r is not None else (dst, 0)
            elif dst.startswith("s") and op.startswith("s_"):
                sval[dst] = (dst, 0)        # clobbered by some other scalar op

        # --- track m0 = base_register + immediate slot ----------------------
        # The BASE REGISTER selects the LDS buffer (ping-pong / triple-buffer);
        # the immediate is the intra-buffer slot. Keep them separate so the
        # buffer stride is the base-chain delta, not gcd'd with slot offsets.
        if ops and ops[0].strip().split()[0].lower() == "m0":
            if op in ("s_add_u32", "s_add_i32") and len(ops) >= 3:
                a, b = _val(ops[1], sval), _val(ops[2], sval)
                ai, bi = _imm(ops[1]), _imm(ops[2])
                if ai is not None and bi is None:        # imm + reg
                    m0_base, m0_imm = b, ai
                elif bi is not None and ai is None:       # reg + imm
                    m0_base, m0_imm = a, bi
                elif ai is None and bi is None:           # reg + reg: unfoldable
                    m0_base, m0_imm = None, 0
                else:                                     # imm + imm (pure const)
                    m0_base, m0_imm = (None, ai + bi), 0
            elif op == "s_mov_b32" and len(ops) >= 2:
                m0_base, m0_imm = _val(ops[1], sval), 0
            else:
                m0_base, m0_imm = None, 0

        # --- record lds-loads (writes) and ds_reads (reads) in scope --------
        in_scope = scope_idxs is None or ln.idx in scope_idxs
        if not in_scope:
            continue
        if target.is_lds_load(op, ops):
            writes.append((ln.idx, m0_base, m0_imm))
        elif target.classify(op, ops) is Kind.DS_READ:
            reads.append((ln.idx, _read_offset(ops)))

    return _assign_buffers(writes, reads)


def _assign_buffers(writes, reads) -> LdsModel:
    model = LdsModel()
    if not writes or not reads:
        return model

    # All write BASE REGISTERS must share one symbolic LDS root + resolved const.
    if any(base is None for _, base, _ in writes):
        return model                                   # unresolved -> fallback
    roots = {base[0] for _, base, _ in writes}
    if len(roots) != 1:
        return model
    base_min = min(base[1] for _, base, _ in writes)
    distinct_bases = sorted({base[1] - base_min for _, base, _ in writes})

    # Buffer stride = gcd of the base-register deltas (the add-chain step). This
    # excludes the intra-buffer immediate slots, which are < stride.
    stride = 0
    for v in distinct_bases:
        stride = gcd(stride, v)
    if stride <= 0:
        return model
    if any(off < 0 for _, off in reads):
        return model
    # intra-buffer immediates must stay within a buffer (sanity)
    if any(imm < 0 or imm >= stride for _, _, imm in writes):
        return model

    model.stride = stride
    model.write_idx = {idx: (base[1] - base_min) // stride
                       for idx, base, _imm in writes}
    model.read_idx = {idx: off // stride for idx, off in reads}
    n = max(list(model.write_idx.values()) + list(model.read_idx.values())) + 1
    model.n_buffers = n
    # sanity: every read band must be produced by some write band
    wbands = set(model.write_idx.values())
    if not set(model.read_idx.values()) <= wbands:
        return model                                   # bands disagree -> fallback
    model.resolved = True
    return model
