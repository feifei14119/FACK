"""Cross-iteration prefetch recognition + the hoist-only reorder guard.

Recognition: a load whose result is consumed by an instruction sitting EARLIER
in the body (loop-carried / live-in) is a prefetch; a load consumed later in the
same body is not. Guard: with ``protect_prefetch=True`` a recognised prefetch
load may be hoisted (earlier) but never sunk (later), so a reschedule cannot
scatter the design-time prefetch schedule. Default (off) leaves moves unchanged.
"""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.editor import RegionEditor, SkipReason
from reorder.model import Kind, LineKind

MFMA = "v_mfma_f32_16x16x32_fp8_fp8"

# body: two MFMA read v[4:7]/v[8:11] at the TOP (live-in -> previous iteration);
# the loads that refill them sit BELOW -> cross-iteration prefetch. v[60:63] has
# no reader (not prefetch) and gives hoist slack; v[50:53] is consumed by an MFMA
# AFTER it (same iteration) -> NOT prefetch.
#   pos0 mfma <- v[4:7]      pos1 mfma <- v[8:11]
#   pos2 load v[60:63]       pos3 load v[4:7]   pos4 load v[8:11]
#   pos5 load v[50:53]       pos6 mfma <- v[50:53]
_SRC = """.text
k:
  {m} v[36:39], a[0:1], v[4:7], v[36:39]
  {m} v[40:43], a[2:3], v[8:11], v[40:43]
  buffer_load_dwordx4 v[60:63], v66, s[0:3], 0 offen
  buffer_load_dwordx4 v[4:7],   v64, s[0:3], 0 offen
  buffer_load_dwordx4 v[8:11],  v65, s[0:3], 0 offen
  buffer_load_dwordx4 v[50:53], v67, s[0:3], 0 offen
  {m} v[44:47], a[4:5], v[50:53], v[44:47]
  s_endpgm
""".format(m=MFMA)


def _editor(src=_SRC, **kw):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    reg = regions.analyze(prog, t).regions[0]
    return RegionEditor(prog, t, reg, treat_waitcnt_as_fence=False, **kw)


def _loads(ed):
    return [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD]


class TestRecognition(unittest.TestCase):
    def test_live_in_loads_are_prefetch(self):
        ed = _editor()
        info = ed.prefetch_info()
        loads = _loads(ed)                       # [v60, v4, v8, v50] in order
        self.assertIn(loads[1], info.producers)  # v[4:7] consumed at top
        self.assertIn(loads[2], info.producers)  # v[8:11] consumed at top
        self.assertEqual(len(info.producers), 2)

    def test_same_iteration_load_is_not_prefetch(self):
        ed = _editor()
        info = ed.prefetch_info()
        loads = _loads(ed)
        self.assertNotIn(loads[3], info.producers)  # v[50:53] consumed later
        self.assertNotIn(loads[0], info.producers)  # v[60:63] never consumed

    def test_edges_point_to_earlier_consumer(self):
        ed = _editor()
        info = ed.prefetch_info()
        pos = {i: k for k, i in enumerate(ed.order)}
        self.assertTrue(info.edges)
        for e in info.edges:
            self.assertLess(pos[e.consumer], pos[e.producer])  # consumer is earlier
            self.assertGreater(e.distance, 0)


class TestGuard(unittest.TestCase):
    def test_guard_blocks_sinking_prefetch(self):
        ed = _editor(protect_prefetch=True)
        loads = _loads(ed)
        last = ed.anchors(Kind.MFMA)[-1]         # sink target near the body end
        d = ed.move_after(loads[1], last, strict=False)
        self.assertFalse(d.changed)              # hoist-only: sink rejected

    def test_guard_still_allows_hoisting_prefetch(self):
        ed = _editor(protect_prefetch=True)
        loads = _loads(ed)
        d = ed.move_before(loads[1], loads[0], strict=False)  # v[4:7] before v[60:63]
        self.assertTrue(d.changed)               # earlier == more overlap == allowed

    def test_guard_does_not_pin_non_prefetch_loads(self):
        ed = _editor(protect_prefetch=True)
        loads = _loads(ed)
        first = ed.anchors(Kind.MFMA)[0]
        d = ed.move_before(loads[3], first, strict=False)  # v[50:53] free to move
        self.assertTrue(d.changed)

    def test_default_off_allows_sinking(self):
        ed = _editor()                            # protect_prefetch defaults False
        loads = _loads(ed)
        last = ed.anchors(Kind.MFMA)[-1]
        d = ed.move_after(loads[1], last, strict=False)
        self.assertTrue(d.changed)

    def test_skip_reason_reported(self):
        ed = _editor(protect_prefetch=True)
        loads = _loads(ed)
        anchors = ed.anchors(Kind.MFMA)
        rep = ed.propose_layouts(anchors, [{len(anchors) - 1: [loads[1]]}])[0]
        reasons = [p.reason for p in rep.skipped]
        self.assertIn(SkipReason.PREFETCH_PROTECTED, reasons)


_GEMM = "client/poc_kl/fp8_blockscale_gemm/shader/fp8gemm_blockscase_32mx1_32nx4.s"


@unittest.skipUnless(os.path.exists(_GEMM), "real gemm seed not present")
class TestRealGemm(unittest.TestCase):
    def test_recognises_both_paths(self):
        with open(_GEMM) as fh:
            prog = parser.parse(fh.read())
        t = Gfx942Target.from_program(prog)
        loop = [r for r in regions.analyze(prog, t).regions
                if r.kind is regions.RegionKind.LOOP][0]
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False,
                          protect_prefetch=True)
        info = ed.prefetch_info()
        self.assertGreater(len(info.producers), 0)
        vias = {e.via for e in info.edges}
        self.assertIn("reg", vias)
        self.assertIn("lds", vias)               # triple-buffered LDS prefetch
        # every guarded producer must actually be a load
        for p in info.producers:
            self.assertIs(ed.kind_of(p), Kind.VMEM_LOAD)


if __name__ == "__main__":
    unittest.main()
