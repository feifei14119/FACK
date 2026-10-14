"""gfx942 opcode classification: mnemonic -> (Kind, WaitType) and predicates.

Reference: amdgpu-asm-codebase/llvm-isa/gfx942 (instruction families) and
13-waitcnt / counter semantics.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from reorder.model import Kind, WaitType
from . import operands as ops


# --- branch / control mnemonics -----------------------------------------
_BRANCH_EXACT = {
    "s_branch", "s_setpc_b64", "s_swappc_b64", "s_endpgm",
    "s_endpgm_saved", "s_call_b64", "s_return",
}
_BRANCH_PREFIX = ("s_cbranch",)

_WAITCNT_OPS = {
    "s_waitcnt", "s_waitcnt_vscnt", "s_waitcnt_vmcnt",
    "s_waitcnt_expcnt", "s_waitcnt_lgkmcnt",
}


def is_branch(opcode: str) -> bool:
    if opcode in _BRANCH_EXACT:
        return True
    return any(opcode.startswith(p) for p in _BRANCH_PREFIX)


def is_terminator(opcode: str) -> bool:
    """Unconditional control transfer that ends a basic block with no fallthrough."""
    return opcode in ("s_branch", "s_endpgm", "s_setpc_b64", "s_return")


def writes_m0(opcode: str, operands: List[str]) -> bool:
    if not operands:
        return False
    first = operands[0].strip().split()[0] if operands[0].strip() else ""
    return first.lower() == "m0"


def classify(opcode: str, operands: List[str]) -> Tuple[Kind, WaitType]:
    """Return (semantic Kind, WaitType) for a gfx942 instruction."""
    op = opcode.lower()

    # control flow
    if op in _WAITCNT_OPS:
        return Kind.WAITCNT, WaitType.NONE
    if op == "s_barrier":
        return Kind.BARRIER, WaitType.NONE
    if op == "s_nop":
        return Kind.NOP, WaitType.NONE
    if is_branch(op):
        return Kind.BRANCH, WaitType.NONE

    # matrix engine -- writes tracked by hardware scoreboard, NOT waitcnt
    if op.startswith("v_mfma") or op.startswith("v_smfmac"):
        return Kind.MFMA, WaitType.NONE

    # set m0 (e.g. s_add_u32 m0, ... / s_mov_b32 m0, ...)
    if writes_m0(op, operands):
        return Kind.SET_M0, WaitType.NONE

    # scalar memory -> lgkmcnt
    if op.startswith("s_load") or op.startswith("s_buffer_load") or \
       op.startswith("s_store") or op.startswith("s_buffer_store") or \
       op.startswith("s_scratch_") or op.startswith("s_atomic") or \
       op.startswith("s_dcache"):
        return Kind.SMEM, WaitType.LGKM

    # LDS (ds_*) -> lgkmcnt
    if op.startswith("ds_"):
        if "read" in op or "load" in op:
            return Kind.DS_READ, WaitType.LGKM
        if "write" in op or "store" in op:
            return Kind.DS_WRITE, WaitType.LGKM
        return Kind.DS_WRITE, WaitType.LGKM  # atomics etc. (conservative)

    # VMEM: buffer / global / flat / scratch
    if op.startswith(("buffer_", "global_", "flat_", "scratch_")):
        is_store = "store" in op
        is_load = "load" in op
        is_atomic = "atomic" in op
        if is_load or (op.startswith("buffer_") and "_lds" in op):
            return Kind.VMEM_LOAD, WaitType.VM
        if is_store:
            return Kind.VMEM_STORE, WaitType.VS
        if is_atomic:
            # atomic with return value reads back -> vmcnt; otherwise store -> vscnt.
            # heuristic: opcodes ending in _rtn return a value.
            if op.endswith("_rtn") or "_rtn_" in op:
                return Kind.VMEM_LOAD, WaitType.VM
            return Kind.VMEM_STORE, WaitType.VS
        return Kind.OTHER, WaitType.NONE

    # plain ALU
    if op.startswith("v_"):
        return Kind.VALU, WaitType.NONE
    if op.startswith("s_"):
        return Kind.SALU, WaitType.NONE

    return Kind.OTHER, WaitType.NONE


def has_register_dest(opcode: str, kind: Kind) -> bool:
    """True if operand[0] is a written register destination.

    Critical for correctness: marking a *source* as a dest would drop a RAW
    edge. Notably ``s_cmp*`` / ``s_store*`` print a source in operand[0] and
    write only an implicit result (scc / memory), so they have no reg dest.
    """
    op = opcode.lower()
    if kind in (Kind.VMEM_STORE, Kind.DS_WRITE, Kind.BRANCH, Kind.BARRIER,
                Kind.NOP, Kind.WAITCNT, Kind.SET_M0, Kind.OTHER, Kind.UNKNOWN):
        # SET_M0 dest (m0) is handled explicitly as an implicit def, not op[0]
        return kind is Kind.SET_M0  # m0 is operand[0]; keep it a dest
    if kind is Kind.SMEM:
        return op.startswith(("s_load", "s_buffer_load")) or op.endswith("_rtn")
    if kind is Kind.SALU:
        return not op.startswith(("s_cmp", "s_cmpk", "s_bitcmp"))
    # VMEM_LOAD / DS_READ / VALU / MFMA write operand[0]
    return True


def is_lds_load(opcode: str, operands: List[str]) -> bool:
    """buffer/global load with the ``lds`` modifier writes LDS (counts vmcnt)."""
    op = opcode.lower()
    if not op.startswith(("buffer_", "global_")):
        return False
    return "_lds" in op or ops.is_lds_modifier(operands)


# --- implicit operands (not printed in the operand list) -----------------
# scc is written by most scalar compares and scalar ALU carry/logic ops, and
# read by the carry-chain / select / conditional-branch ops. Modeling it keeps
# e.g. an s_addc_u32 correctly ordered after its s_add_u32 producer.
_SCC_READERS = {
    "s_addc_u32", "s_subb_u32", "s_cselect_b32", "s_cselect_b64",
    "s_cbranch_scc0", "s_cbranch_scc1", "s_cmovk_i32",
    "s_cmov_b32", "s_cmov_b64",
}
_SCC_WRITE_PREFIXES = (
    "s_cmp_", "s_cmpk_", "s_bitcmp",
    "s_add_", "s_addc_", "s_sub_", "s_subb_",
    "s_and_", "s_or_", "s_xor_", "s_andn2_", "s_orn2_",
    "s_nand_", "s_nor_", "s_xnor_",
    "s_lshl_", "s_lshr_", "s_ashr_", "s_bfe_", "s_bfm_",
    "s_not_", "s_wqm_", "s_quadmask_", "s_bcnt_", "s_abs_",
)
# s_add_u32 / s_addc_u32 etc. write scc; s_addk/s_mul do not -> handled by set
_SCC_NO_WRITE = {"s_mul_i32", "s_mul_hi_u32", "s_mul_hi_i32"}


def writes_scc(opcode: str) -> bool:
    op = opcode.lower()
    if op in _SCC_NO_WRITE:
        return False
    return any(op.startswith(p) for p in _SCC_WRITE_PREFIXES)


def reads_scc(opcode: str) -> bool:
    return opcode.lower() in _SCC_READERS


def writes_exec(opcode: str, operands: List[str]) -> bool:
    """exec-modifying ops act as scheduling fences (they gate every later
    vector op's active lanes)."""
    op = opcode.lower()
    if "saveexec" in op:
        return True
    if op.startswith("v_cmpx"):          # VOPC compare-and-set-exec
        return True
    first = operands[0].strip().split()[0].lower() if (operands and operands[0].strip()) else ""
    if first.startswith("exec"):
        return True
    return False


# vcc (carry / mask) -- on gfx942 it is usually an explicit operand, but it is
# ALSO the implicit carry-OUT of the carry ALU ops and the implicit carry-IN /
# mask of the select / extended-arith readers. Modelling it as an implicit
# def/use is conservative (it only adds RAW/WAW/WAR ordering, never drops one):
# e.g. it keeps a v_cndmask correctly ordered after the v_add_co_u32 whose carry
# it consumes, even when the v_add wrote vcc only implicitly.
_VCC_WRITE_PREFIXES = (
    "v_add_co_", "v_addc_co_", "v_sub_co_", "v_subrev_co_",
    "v_subb_co_", "v_subbrev_co_", "v_div_scale_",
)
_VCC_READERS = {
    "v_cndmask_b32",
    "v_addc_co_u32", "v_subb_co_u32", "v_subbrev_co_u32",
    "v_div_fmas_f32", "v_div_fmas_f64",
}


def writes_vcc(opcode: str) -> bool:
    return any(opcode.lower().startswith(p) for p in _VCC_WRITE_PREFIXES)


def reads_vcc(opcode: str) -> bool:
    return opcode.lower() in _VCC_READERS


def implicit_defs(opcode: str, operands: List[str]):
    d = set()
    if writes_scc(opcode):
        d.add("scc")
    if writes_vcc(opcode):
        d.add("vcc")
    return d


def implicit_uses(opcode: str, operands: List[str]):
    u = set()
    if reads_scc(opcode):
        u.add("scc")
    if reads_vcc(opcode):
        u.add("vcc")
    return u


# m0 is consumed implicitly by buffer/global ...lds loads (m0 = LDS write
# offset) and by the gws/sendmsg/movrel family.
_M0_CONSUMER_SUBSTR = ("gws", "movrel", "swizzle")


def reads_m0(opcode: str, operands: List[str]) -> bool:
    if is_lds_load(opcode, operands):
        return True
    op = opcode.lower()
    if op == "s_sendmsg":
        return True
    return any(s in op for s in _M0_CONSUMER_SUBSTR)


# --- MFMA result write-after latency (FALLBACK table) ---------------------
# Minimum number of issue slots that must separate an MFMA writing an
# accumulator VGPR from a NON-MFMA instruction that reads it (back-to-back MFMA
# accumulation is pipelined -> distance 1; a VALU/VMEM/DS consumer reading the
# result too soon gets a stale value).
#
# PRIMARY source is now SEED-DERIVED: edges.py auto-calibrates the latency per
# MFMA opcode from the seed's own tightest MFMA-write -> non-MFMA-read spacing
# (the seed is known-correct, so its minimum gap is the empirically-safe value;
# this is how 16x16x32 == 3 was found, and a gap of 2 fails on MI308X HW). This
# table is only the FALLBACK for an MFMA opcode that has NO consumer in the
# seed, and the value ForcedNopPass uses to pad a too-tight seed. Other shapes
# are proportional estimates -- aggressive strategies on them are HW-culled.
MFMA_READ_LATENCY: Dict[str, int] = {
    "16x16x16": 3,
    "16x16x32": 3,
    "32x32x": 6,
    "4x4x": 2,
}
_DEFAULT_MFMA_LATENCY = 0  # unknown shape -> no extra distance (safe no-op)


def mfma_read_latency(opcode: str) -> int:
    op = opcode.lower()
    for key, val in MFMA_READ_LATENCY.items():
        if key in op:
            return val
    return _DEFAULT_MFMA_LATENCY
