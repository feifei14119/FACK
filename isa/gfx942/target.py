"""gfx942 concrete Target implementation.

Wires together the operand model, opcode classifier and counter model behind
the architecture-agnostic Target contract consumed by reorder/*.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from reorder.model import Kind, Line

from . import classify as _cls
from . import edges as _edges
from . import operands as _ops
from .counters import Gfx942CounterModel


class Gfx942Target:
    name = "gfx942"

    def __init__(self, aliases: Optional[Dict[str, int]] = None) -> None:
        self._aliases = aliases or {}
        self._counter_model = Gfx942CounterModel()

    def candidate_providers(self):
        """Optional CPU candidate generators, shared by every client on this ISA."""
        from .candidates import salu_chains, repeated_salu_chains, repeated_operand_prefetch
        return {"gfx942_salu_chains": salu_chains,
                "gfx942_repeated_salu_chains": repeated_salu_chains,
                "gfx942_repeated_operand_prefetch": repeated_operand_prefetch}

    @classmethod
    def from_program(cls, program) -> "Gfx942Target":
        """Build a target whose alias map is populated from the program's
        ``.set name, value`` directives (best-effort integer values)."""
        pairs = []
        for ln in program.lines:
            if ln.directive == ".set":
                body = ln.raw.split(".set", 1)[1]
                if "," in body:
                    name, value = body.split(",", 1)
                    pairs.append((name.strip(), value.strip()))
        return cls(aliases=_ops.collect_aliases(pairs))

    # --- lexing / operands -------------------------------------------------
    def register_prefixes(self) -> Set[str]:
        return {"s", "v", "a", "acc"}

    def parse_operands(self, opcode: str, operand_strs: List[str]) -> Tuple[_ops.RegSet, _ops.RegSet]:
        """Return (defs, uses). Convention: the first operand field is the
        destination for instructions that write a register; everything else is
        a use. Memory/branch/no-dest forms treat all fields as uses.

        This is a best-effort def/use split sufficient for M1 (regions + waitcnt
        read-only sim); precise per-opcode operand roles are refined in M2.
        """
        defs: Set = set()
        uses: Set = set()
        kind, _ = _cls.classify(opcode, operand_strs)

        # LDS-direct VMEM returns data to LDS; operand[0] is an address,
        # not a VGPR result. Keep it as a use for RAW/WAR scheduling edges.
        has_dest = (_cls.has_register_dest(opcode, kind)
                    and not _cls.is_lds_load(opcode, operand_strs))
        for i, field_str in enumerate(operand_strs):
            units = _ops.parse_operand_field(field_str, self._aliases)
            if i == 0 and has_dest:
                defs |= units
            else:
                uses |= units
        # MFMA / accumulate forms also read their destination (src2 == dst)
        if kind is Kind.MFMA:
            uses |= defs
        return _ops.RegSet(defs), _ops.RegSet(uses)

    # --- classification ----------------------------------------------------
    def def_use(self, opcode: str, operands: List[str]):
        """Return (defs, uses) as register-unit sets including implicit operands
        (scc, m0, ...). Used by the dependency graph (M2)."""
        defs_rs, uses_rs = self.parse_operands(opcode, operands)
        defs = set(defs_rs.units) | _cls.implicit_defs(opcode, operands)
        uses = set(uses_rs.units) | _cls.implicit_uses(opcode, operands)
        return defs, uses

    def classify(self, opcode: str, operands: List[str]) -> Kind:
        kind, _ = _cls.classify(opcode, operands)
        return kind

    def wait_type(self, opcode: str, operands: List[str]):
        _, wt = _cls.classify(opcode, operands)
        return wt

    def is_lds_load(self, opcode: str, operands: List[str]) -> bool:
        return _cls.is_lds_load(opcode, operands)

    def lds_roundtrip_model(self, instr_lines, scope_idxs=None):
        """Resolve the LDS multi-buffer structure for an instruction stream so
        the waitcnt recompute can bind each ``ds_read`` to the lds-loads that
        fill the buffer band it reads (M5). ``instr_lines`` should include the
        prologue (where the LDS base chain is established); ``scope_idxs`` limits
        which loads/reads are recorded. Returns an ``LdsModel`` (its ``resolved``
        flag is False when the structure can't be recovered, and the recompute
        then falls back to the conservative single-bucket guard)."""
        from .lds import build_lds_model
        return build_lds_model(instr_lines, self, scope_idxs=scope_idxs)

    # --- control flow ------------------------------------------------------
    def is_branch(self, line: Line) -> bool:
        return bool(line.opcode) and _cls.is_branch(line.opcode.lower())

    def is_conditional_branch(self, line: Line) -> bool:
        return bool(line.opcode) and line.opcode.lower().startswith("s_cbranch")

    def is_terminator(self, line: Line) -> bool:
        return bool(line.opcode) and _cls.is_terminator(line.opcode.lower())

    def branch_target(self, line: Line) -> Optional[str]:
        if not self.is_branch(line) or not line.operands:
            return None
        op = line.opcode.lower()
        if op in ("s_endpgm", "s_return", "s_setpc_b64", "s_swappc_b64"):
            return None
        # branch target is the last operand label
        tok = line.operands[-1].strip().split()[0] if line.operands[-1].strip() else ""
        return tok or None

    # --- counters ----------------------------------------------------------
    def counter_model(self) -> Gfx942CounterModel:
        return self._counter_model

    # --- dependencies (M2) -------------------------------------------------
    def build_edges(self, nodes, graph) -> None:
        _edges.build_edges(self, nodes, graph)

    def bundles(self, nodes) -> List:
        return _edges.bundles(self, nodes)

    # --- fixups / verification / analysis (M4) -----------------------------
    def fixup_pipeline(self, region=None, recompute_waitcnt: bool = False,
                       opt_level=None) -> List:
        """Ordered gfx942 fixup passes.

        Default (warm, hand-tuned kernels): keep existing waits as fences and
        only apply ForcedNop -- this is always correct and never disturbs the
        hand-tuned (loop-carried) ``s_waitcnt`` values.

        ``recompute_waitcnt=True`` (cold-start / aggressive cross-wait reorder):
        also drop and recompute the waits for ``region`` with the LOOP-AWARE
        score-based recompute (cross-iteration fixpoint).

        ``opt_level`` (see ``reorder.optlevel``) tunes the recompute's barrier
        LDS-release fence: L0 = drain ALL lds-loads (robust), L1 = band
        look-ahead (default), L2 = band look-ahead (reorder is driven by the
        caller, not this pass). Only meaningful when ``recompute_waitcnt``.

        M5 (gfx942 HW-validated): from-scratch recompute is now correct. The two
        memory-ordering constraints invisible to register tracking are modelled:
          * LDS round-trip (buffer_load...lds -> ds_read) -- bound per LDS buffer
            band via the m0 base-chain resolver (see lds.py), so each ds_read
            waits (vmcnt) for the loads that fill the band it reads;
          * barrier LDS-release fence -- lgkmcnt(0) + vmcnt draining the lds-loads
            of the bands READ before the next barrier (cross-wave LDS coherence;
            other bands' prefetch stays in flight). This barrier fence was the
            actual root cause of M4's rare high-k race.
        recompute_only validated on MI308X (gfx942): k=2048/4096: 50/50;
        k=8192/16384: 100/100 PASS (M4 broken recompute was 2/10 @ k=2048);
        ~3879 vs hand ~3663 GFLOPS @ k=4096. See steps/M5-lds-slot-precise-modeling.md.
        """
        from .passes import WaitcntRecomputePass, ForcedNopPass
        passes = []
        if recompute_waitcnt:
            passes.append(WaitcntRecomputePass(region=region, opt_level=opt_level))
        passes.append(ForcedNopPass())
        return passes

    def post_recompute_passes(self) -> List:
        """Hazard passes run after every candidate's waitcnt recompute."""
        from .passes import ForcedNopPass
        return [ForcedNopPass()]

    def invariants(self) -> List:
        from .invariants import BarrierCountLocked, WaitcntEncodable
        return [BarrierCountLocked(), WaitcntEncodable(self._counter_model)]

    def perf_counter_schema(self) -> Dict[str, object]:
        """ATT instruction ``category`` -> bottleneck dimension (see
        proj/amdgpu-dump-parsing.md §6). Consumed by analysis/."""
        from .perf_schema import GFX942_ATT_SCHEMA
        return GFX942_ATT_SCHEMA

    def kernel_symbols(self, program) -> List[str]:
        """Kernel entry symbols defined in the program, in order. The engine is
        kernel-agnostic: callers (e.g. the ATT capture filter) derive WHICH
        kernel to act on from the .s being optimized rather than hardcoding a
        name. On AMDGPU the canonical marker is the ``.amdhsa_kernel <name>``
        directive (NOT ``.end_amdhsa_kernel``)."""
        out: List[str] = []
        for ln in program.lines:
            if ln.directive == ".amdhsa_kernel":
                parts = ln.raw.split()
                if len(parts) >= 2:
                    out.append(parts[1])
        return out


def _factory() -> Gfx942Target:
    return Gfx942Target()
