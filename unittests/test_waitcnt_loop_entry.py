"""First-iteration waits must protect entry loads as well as loop-carried loads."""
import pytest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions, waitcnt
from reorder.model import LineKind
from reorder.verifier import Verifier


# Entry has one newer VMEM event after the band-1 fill; the repeated body has
# two. A steady-state vmcnt(2) is therefore insufficient on the first visit.
LDS_ENTRY = """.text
.type kernel, @function
kernel:
  s_add_u32 s2, 0, s0
  s_add_u32 s3, 256, s2
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  buffer_load_dword v30, v8, s[4:7], 0 offen
loop:
  s_waitcnt vmcnt(1) lgkmcnt(0)
  s_barrier
  ds_read_b32 v10, v20 offset:256
  s_add_u32 m0, 0, s2
  buffer_load_dword v0, s[4:7], 0 offen lds
  s_add_u32 m0, 0, s3
  buffer_load_dword v1, s[4:7], 0 offen lds
  buffer_load_dword v30, v8, s[4:7], 0 offen
  buffer_load_dword v31, v8, s[4:7], 0 offen
  s_cbranch_scc0 loop
  s_waitcnt vmcnt(0) lgkmcnt(0)
  s_endpgm
"""

REG_ENTRY = """.text
kernel:
  buffer_load_dword v1, v8, s[4:7], 0 offen
  buffer_load_dword v30, v8, s[4:7], 0 offen
loop:
  s_waitcnt vmcnt(1)
  v_mov_b32 v10, v1
  buffer_load_dword v1, v8, s[4:7], 0 offen
  buffer_load_dword v30, v8, s[4:7], 0 offen
  buffer_load_dword v31, v8, s[4:7], 0 offen
  s_cbranch_scc0 loop
  s_waitcnt vmcnt(0)
  s_endpgm
"""


def _load(src):
    prog = parser.parse(src)
    target = Gfx942Target.from_program(prog)
    analysis = regions.analyze(prog, target)
    loop = next(r for r in analysis.regions if r.kind is regions.RegionKind.LOOP)
    return prog, target, loop


def _verify(prog, target):
    return Verifier(target, analysis=regions.analyze(prog, target)).verify(prog)


def _pending_band1_at_barriers(prog, target, copies=3):
    """Independent FIFO trace for this fixture, without the engine scoreboard.

    Every VMEM in the fixture contributes one event. The v1 LDS loads fill the
    band read after each barrier; no such event may remain pending at release.
    """
    instr = [ln for ln in prog.lines if ln.kind in (LineKind.INSTR, LineKind.LABEL)]
    entry = next(i for i, ln in enumerate(instr) if ln.label == "kernel")
    header = next(i for i, ln in enumerate(instr) if ln.label == "loop")
    latch = next(i for i, ln in enumerate(instr)
                 if ln.opcode == "s_cbranch_scc0" and ln.operands == ["loop"])
    pending, observed = [], []
    for ln in instr[entry:header] + instr[header:latch + 1] * copies:
        if ln.opcode == "buffer_load_dword":
            pending.append(target.is_lds_load(ln.opcode, ln.operands)
                           and ln.operands[0] == "v1")
        elif ln.opcode == "s_waitcnt":
            count = target.counter_model().parse_wait(ln.opcode, ln.operands).targets.get("vm")
            if count is not None and len(pending) > count:
                del pending[:len(pending) - count]
        elif ln.opcode == "s_barrier":
            observed.append(sum(pending))
    return observed


def test_minimal_lds_example_distinguishes_entry_from_steady_state():
    prog, target, _ = _load(LDS_ENTRY.replace("vmcnt(1)", "vmcnt(2)"))
    # The defect affects precisely the first iteration; repeated-body-only
    # checks cannot detect it, despite being sufficient on later iterations.
    assert _pending_band1_at_barriers(prog, target) == [1, 0, 0]


@pytest.mark.parametrize("whole_kernel", [False, True])
def test_recompute_protects_entry_and_steady_state_lds(whole_kernel):
    prog, target, loop = _load(LDS_ENTRY)
    before = [ln.raw for ln in prog.instr_lines() if ln.opcode != "s_waitcnt"]
    if whole_kernel:
        waitcnt.recompute_cfg(prog, target)
    else:
        waitcnt.recompute(prog, target, region=loop)
    assert _pending_band1_at_barriers(prog, target) == [0, 0, 0]
    assert [ln.raw for ln in prog.instr_lines() if ln.opcode != "s_waitcnt"] == before
    assert _verify(prog, target).ok


@pytest.mark.parametrize("src, message", [(LDS_ENTRY, "LDS round-trip"),
                                          (REG_ENTRY, "use of ('v', 1) not synced")],
                         ids=["lds", "register"])
def test_verifier_rejects_first_iteration_only_underwait(src, message):
    prog, target, _ = _load(src)
    assert _verify(prog, target).ok
    broken, target, _ = _load(src.replace("vmcnt(1)", "vmcnt(2)"))
    result = _verify(broken, target)
    assert not result.ok
    assert any(message in v for v in result.violations), result.violations


def test_register_recompute_preserves_entry_load_requirement():
    prog, target, loop = _load(REG_ENTRY)
    waitcnt.recompute(prog, target, region=loop)
    assert _verify(prog, target).ok


def test_loop_model_excludes_other_functions_and_unedited_suffix():
    # An unrelated unresolved LDS address must not poison this loop's precise
    # model. Function declarations delimit entry state, even in a .text with
    # several kernels; the unedited suffix is outside the model's scope too.
    foreign = """.text
.type other, @function
other:
  s_add_u32 m0, s7, s8
  buffer_load_dword v1, s[4:7], 0 offen lds
  s_endpgm
"""
    suffix = """  s_add_u32 m0, s7, s8
  buffer_load_dword v1, s[4:7], 0 offen lds
"""
    solo, target, loop = _load(LDS_ENTRY)
    waitcnt.recompute(solo, target, region=loop)
    combined, target, loop = _load(foreign + LDS_ENTRY + suffix)
    untouched = [ln.raw for ln in combined.lines
                 if ln.idx < next(l.idx for l in combined.lines if l.label == "kernel")]
    waitcnt.recompute(combined, target, region=loop)
    assert _pending_band1_at_barriers(combined, target) == [0, 0, 0]
    assert [ln.raw for ln in combined.lines[:len(untouched)]] == untouched
    def loop_waits(prog):
        active, specs = False, []
        for ln in prog.lines:
            active |= ln.label == "loop"
            if active and ln.opcode == "s_waitcnt":
                specs.append(target.counter_model().parse_wait(ln.opcode, ln.operands).targets)
            if active and ln.opcode == "s_cbranch_scc0":
                break
        return specs
    assert loop_waits(combined) == loop_waits(solo)
