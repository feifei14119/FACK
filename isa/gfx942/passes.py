"""gfx942 fixup passes (the ordered ``fixup_pipeline()`` for this architecture).

  WaitcntRecomputePass  -- drop existing waits and recompute minimal correct
                           s_waitcnt / s_waitcnt_vscnt from the dependency graph
                           (delegates to the architecture-agnostic
                           reorder.waitcnt.recompute + this target's CounterModel).
  ForcedNopPass         -- gfx942 MFMA write-after latency: if a non-MFMA reader
                           of an MFMA accumulator is issued too soon, pad with
                           ``s_nop``. Never adds/removes barriers or branches.

Other architectures would register different passes (s_delay_alu, s_clause,
register-bank switch, ...) without touching the core engine.
"""
from __future__ import annotations

from typing import Dict, List

from reorder import waitcnt as _waitcnt
from reorder.model import Kind, Line, LineKind, Program
from reorder.passes import LineDiff, snapshot


class WaitcntRecomputePass:
    name = "waitcnt_recompute"

    def __init__(self, region=None, opt_level=None):
        # region=None -> recompute over the whole .text instruction stream
        self.region = region
        # opt_level (reorder.optlevel) -> barrier fence aggressiveness; None=default
        self.opt_level = opt_level

    def run(self, program: Program, target) -> LineDiff:
        before = snapshot(program)
        _waitcnt.recompute(program, target, region=self.region,
                           opt_level=self.opt_level)
        return LineDiff(self.name, before, list(program.lines))


from . import classify as _cls

# MFMA write->use latency lives in ONE place (classify.MFMA_READ_LATENCY): the
# static dep graph uses it as a min-distance edge constraint (so the reorder
# never hoists a consumer into the latency window), and this pass uses the same
# numbers to pad s_nop when the *seed* itself is already too tight.
_mfma_latency = _cls.mfma_read_latency


class ForcedNopPass:
    name = "forced_nop"

    def run(self, program: Program, target) -> LineDiff:
        before = snapshot(program)
        from reorder import regions
        items = [it.line for it in regions._collect_code_items(program)
                 if it.line.kind is LineKind.INSTR]
        idx_pos = {ln.idx: i for i, ln in enumerate(items)}

        # iid -> number of s_nop slots to insert immediately after it
        inserts: Dict[int, int] = {}
        for i, ln in enumerate(items):
            op = (ln.opcode or "").lower()
            if not (op.startswith("v_mfma") or op.startswith("v_smfmac")):
                continue
            required = _mfma_latency(op)
            if required <= 0:
                continue
            dest, _ = target.def_use(op, ln.operands)
            if not dest:
                continue
            slots = 0
            for j in range(i + 1, len(items)):
                nxt = items[j]
                nop = (nxt.opcode or "").lower()
                k = target.classify(nop, nxt.operands)
                if k in (Kind.MFMA, Kind.BARRIER, Kind.BRANCH):
                    break  # chain continues / hard boundary: hw handles it
                _, uses = target.def_use(nop, nxt.operands)
                if uses & dest:
                    if slots < required:
                        inserts[ln.idx] = required - slots
                    break
                slots += 1
                if slots >= required:
                    break

        if not inserts:
            return LineDiff(self.name, before, before, "no nops needed")

        next_idx = max((ln.idx for ln in program.lines), default=0) + 1
        new_lines: List[Line] = []
        for ln in program.lines:
            new_lines.append(ln)
            if ln.idx in inserts:
                indent = ln.indent or "  "
                for _ in range(inserts[ln.idx]):
                    new_lines.append(Line(idx=next_idx, raw=indent + "s_nop 0",
                                          kind=LineKind.INSTR, indent=indent,
                                          opcode="s_nop", operands=["0"]))
                    next_idx += 1
        program.lines = new_lines
        return LineDiff(self.name, before, list(program.lines),
                        "inserted {} nop groups".format(len(inserts)))
