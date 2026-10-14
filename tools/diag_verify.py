"""Sanity: the M5 verifier passes hand code + recompute candidate, and flags a
deliberately-broken one (lgkmcnt(3) before barrier; loosened ds_read vmcnt)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reorder import parser, regions, waitcnt
from reorder.verifier import Verifier
from reorder.model import LineKind
from isa.gfx942.target import Gfx942Target

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADER = os.path.join(HERE, "client", "poc_kl", "fp8_blockscale_gemm", "shader", "fp8gemm_blockscase_32mx1_32nx4.s")


def check(label, prog, t):
    a = regions.analyze(prog, t)
    res = Verifier(t, reference=None, analysis=a).verify(prog)
    nbar = sum(1 for x in res.violations if "barrier LDS-release" in x)
    nlds = sum(1 for x in res.violations if "ds_read LDS round-trip" in x)
    nreg = len(res.violations) - nbar - nlds
    print("{:30s} ok={} [reg={} barrier_fence={} lds_roundtrip={}]".format(
        label, res.ok, nreg, nbar, nlds))
    return res


def main():
    src = open(SHADER).read()

    # 1. hand code
    prog = parser.parse(src)
    check("hand (baseline)", prog, Gfx942Target.from_program(prog))

    # 2. recompute_only candidate
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    loop = [r for r in regions.analyze(prog, t).regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    check("recompute_only", prog, t)

    # 3. broken: strip every vmcnt/lgkm constraint in the loop (under-sync)
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    cm = t.counter_model()
    for ln in prog.lines:
        if ln.kind is LineKind.INSTR and cm.is_wait((ln.opcode or "").lower()):
            # neuter to a no-op wait (all counters unconstrained-ish: huge targets)
            ln.opcode = "s_nop"
            ln.operands = ["0"]
            ln.raw = "  s_nop 0"
    check("broken (waits stripped)", prog, t)

    # 4. targeted: recompute, then loosen the barrier lgkm fence + drop a ds_read
    #    vmcnt -> must trip the NEW barrier/LDS checks specifically.
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    loop = [r for r in regions.analyze(prog, t).regions if r.kind.value == "loop"][0]
    waitcnt.recompute(prog, t, region=loop)
    cm = t.counter_model()
    bumped_barrier = dropped_ds = False
    new_lines = []
    items = regions._collect_code_items(prog)
    barrier_idxs = {it.line.idx for it in items
                    if t.classify((it.line.opcode or "").lower(), it.line.operands).value == "barrier"}
    prev = None
    for ln in prog.lines:
        op = (ln.opcode or "").lower()
        # loosen the lgkmcnt(0) that immediately precedes a barrier
        if (not bumped_barrier and cm.is_wait(op) and "lgkmcnt(0)" in ln.raw):
            ln.raw = ln.raw.replace("lgkmcnt(0)", "lgkmcnt(8)")
            ln.operands = [ln.raw.strip().split(None, 1)[1]]
            bumped_barrier = True
        # drop the first standalone ds_read vmcnt (a lone "s_waitcnt vmcnt(N)")
        if (not dropped_ds and cm.is_wait(op) and "vmcnt(" in ln.raw
                and "lgkm" not in ln.raw):
            dropped_ds = True
            continue
        new_lines.append(ln)
    prog.lines = new_lines
    check("broken (barrier+lds loosened)", prog, t)


if __name__ == "__main__":
    main()
