"""M5 diagnosis: trace the LDS round-trip waitcnt recompute on the real kernel.

Loads the testcase shader, finds the loop region, runs the loop-aware scoreboard
with detailed per-ds_read tracing, and reports:
  - whether lds-direct loads are detected at all (the suspected `== "lds"` bug)
  - the m0 base/offset of each lds-load and the v34+offset of each ds_read
  - the vmcnt the (current / fixed) conservative guard produces for each ds_read
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parse_file
from reorder import regions
from reorder.model import LineKind
from isa.gfx942.target import Gfx942Target

SHADER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "client", "poc_kl", "fp8_blockscale_gemm", "shader", "fp8gemm_blockscase_32mx1_32nx4.s")


def main():
    prog = parse_file(SHADER)
    target = Gfx942Target.from_program(prog)
    ra = regions.analyze(prog, target)

    print("== regions ==")
    for r in ra.regions:
        print("  {:9s} lines {}..{} {}".format(
            r.kind.value, r.line_start, r.line_end, r.header_label or ""))

    loop = next((r for r in ra.regions if r.kind.value == "loop"), None)
    if loop is None:
        print("NO LOOP FOUND")
        return
    print("\n== loop body lines {}..{} ==".format(loop.line_start, loop.line_end))

    # Detect lds-loads two ways: the buggy waitcnt check vs the correct classify.
    from reorder.waitcnt import _is_lds_direct_load
    lds_buggy = 0
    lds_correct = 0
    ds_reads = 0
    for ln in prog.lines:
        if not (loop.line_start <= ln.idx <= loop.line_end):
            continue
        if ln.kind is not LineKind.INSTR or not ln.opcode:
            continue
        op = ln.opcode.lower()
        if _is_lds_direct_load(op, ln.operands):
            lds_buggy += 1
        if target.is_lds_load(op, ln.operands):
            lds_correct += 1
            print("  LDS-LOAD  idx={:<4} op={:<20} operands={}".format(
                ln.idx, op, ln.operands))
        if target.classify(op, ln.operands).value == "ds_read":
            ds_reads += 1

    print("\nlds-loads via waitcnt._is_lds_direct_load (BUGGY): {}".format(lds_buggy))
    print("lds-loads via target.is_lds_load (CORRECT):        {}".format(lds_correct))
    print("ds_reads in loop body:                             {}".format(ds_reads))

    # --- slot offsets: m0 for lds-loads, offset:N for ds_reads ---
    print("\n== m0 offsets (lds writes) and ds_read offsets (loop body) ==")
    last_m0 = None
    body = [ln for ln in prog.lines
            if loop.line_start <= ln.idx <= loop.line_end
            and ln.kind is LineKind.INSTR and ln.opcode]
    for ln in body:
        op = ln.opcode.lower()
        if op.startswith("s_add") and ln.operands and ln.operands[0].strip().split()[0].lower() == "m0":
            last_m0 = (ln.operands[1].strip(), ln.operands[2].strip() if len(ln.operands) > 2 else "")
        elif target.is_lds_load(op, ln.operands):
            print("  WRITE idx={:<4} {:<12} m0=base[{}]+imm[{}]".format(
                ln.idx, ln.operands[0], last_m0[1] if last_m0 else "?",
                last_m0[0] if last_m0 else "?"))
        elif target.classify(op, ln.operands).value == "ds_read":
            off = "0"
            for f in ln.operands:
                for tok in f.split():
                    if tok.startswith("offset:"):
                        off = tok.split(":", 1)[1]
            base = ln.operands[1].strip().split()[0] if len(ln.operands) > 1 else "?"
            print("  READ  idx={:<4} {:<12} base[{}]+offset[{}]".format(
                ln.idx, ln.operands[0], base, off))

    # --- buffer model + buffer-precise vmcnt per ds_read ---
    from isa.gfx942.lds import build_lds_model
    all_instr = [ln for ln in prog.lines if ln.kind is LineKind.INSTR and ln.opcode]
    body = [ln for ln in prog.lines
            if loop.line_start <= ln.idx <= loop.line_end
            and ln.kind is LineKind.INSTR and ln.opcode]
    scope = {ln.idx for ln in body}
    m = build_lds_model(all_instr, target, scope_idxs=scope)
    print("\n== LDS buffer model: resolved={} stride={} n_buffers={} ==".format(
        m.resolved, m.stride, m.n_buffers))
    print("  write buffers:", sorted(set(m.write_idx.values())) if m.write_idx else [])
    print("  read  buffers:", sorted(set(m.read_idx.values())) if m.read_idx else [])

    from reorder.waitcnt import compute_waits_loop
    need = compute_waits_loop(body, target, lds_model=m)
    print("\n== recomputed vmcnt at ds_reads (buffer-precise, loop fixpoint) ==")
    for ln in body:
        if target.classify((ln.opcode or "").lower(), ln.operands).value == "ds_read":
            spec = need.get(ln.idx, {})
            print("  ds_read idx={:<4} buf={}  -> {}".format(
                ln.idx, m.read_buffer(ln.idx), spec or "(no wait)"))


if __name__ == "__main__":
    main()
