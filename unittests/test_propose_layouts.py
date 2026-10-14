"""M6a tests: AI-directed per-slot layout proposals (RegionEditor.propose_layouts)
+ SkipReason classification. Pure wrapper over set_gap_layout/move_after; these
tests assert heterogeneous placement, non-committing semantics, and that each
rejection carries the right reason code + blocking instruction."""
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.editor import RegionEditor, IllegalMove, SkipReason
from reorder.model import Kind

MFMA = "v_mfma_f32_16x16x32_fp8_fp8"

# 5 MFMA + 4 independent buffer_load, all clustered (cold layout). The loads
# write/read disjoint regs, so each has a wide legal window over the MFMA gaps.
_FIVE_MFMA_FOUR_LOAD = """.text
k:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  {m} v[44:47], a[8:9], a[10:11], v[44:47]
  {m} v[48:51], a[12:13], a[14:15], v[48:51]
  {m} v[52:55], a[16:17], a[18:19], v[52:55]
  buffer_load_dwordx4 v[4:7],   v64, s[0:3], 0 offen
  buffer_load_dwordx4 v[8:11],  v65, s[0:3], 0 offen
  buffer_load_dwordx4 v[12:15], v66, s[0:3], 0 offen
  buffer_load_dwordx4 v[16:19], v67, s[0:3], 0 offen
  s_endpgm
""".format(m=MFMA)


def _editor(src, **kw):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    reg = regions.analyze(prog, t).regions[0]
    return RegionEditor(prog, t, reg, treat_waitcnt_as_fence=False, **kw)


def _loads(ed):
    return [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD]


class TestHeterogeneousPlacement(unittest.TestCase):
    def setUp(self):
        self.ed = _editor(_FIVE_MFMA_FOUR_LOAD)
        self.mfma = self.ed.anchors(Kind.MFMA)
        self.ld = _loads(self.ed)

    def test_2_1_1_layout_all_placed_and_legal(self):
        lay = {0: [self.ld[0], self.ld[1]], 1: [self.ld[2]], 2: [self.ld[3]]}
        rep = self.ed.propose_layouts(self.mfma, [lay])[0]
        self.assertEqual(rep.skipped, [])
        self.assertTrue(rep.all_placed)
        self.assertTrue(rep.legal)
        self.assertEqual([p.slot for p in rep.placed], [0, 0, 1, 2])

    def test_2_0_2_layout_all_placed_and_legal(self):
        lay = {0: [self.ld[0], self.ld[1]], 2: [self.ld[2], self.ld[3]]}
        rep = self.ed.propose_layouts(self.mfma, [lay])[0]
        self.assertEqual(rep.skipped, [])
        self.assertTrue(rep.legal)

    def test_intra_slot_order_preserved(self):
        # applying the proposed layout via set_gap_layout reproduces the intent:
        # slot0 holds [ld0, ld1] in order, right after mfma0.
        lay = {0: [self.ld[0], self.ld[1]], 2: [self.ld[2], self.ld[3]]}
        self.ed.set_gap_layout(self.mfma, lay)
        kinds = [self.ed.kind_of(i).value for i in self.ed.order]
        self.assertEqual(kinds[:4], ["mfma", "vmem_load", "vmem_load", "mfma"])
        self.assertEqual(self.ed.order[1], self.ld[0])
        self.assertEqual(self.ed.order[2], self.ld[1])

    def test_non_committing(self):
        before = list(self.ed.order)
        self.ed.propose_layouts(self.mfma, [
            {0: [self.ld[0], self.ld[1]], 1: [self.ld[2]], 2: [self.ld[3]]},
            {0: [self.ld[0], self.ld[1]], 2: [self.ld[2], self.ld[3]]},
        ])
        self.assertEqual(self.ed.order, before)

    def test_batch_independent_and_ordered(self):
        cands = [
            {0: [self.ld[0]]},
            {1: [self.ld[1]], 2: [self.ld[2]]},
        ]
        reps = self.ed.propose_layouts(self.mfma, cands)
        self.assertEqual(len(reps), 2)
        self.assertEqual(reps[0].layout, cands[0])
        self.assertEqual(reps[1].layout, cands[1])
        for r in reps:
            self.assertTrue(r.all_placed)


class TestSkipReasons(unittest.TestCase):
    def test_slot_out_of_range(self):
        ed = _editor(_FIVE_MFMA_FOUR_LOAD)
        mfma = ed.anchors(Kind.MFMA)
        ld = _loads(ed)
        rep = ed.propose_layouts(mfma, [{9: [ld[0]]}])[0]
        self.assertEqual(len(rep.skipped), 1)
        self.assertEqual(rep.skipped[0].reason, SkipReason.SLOT_OOR)
        self.assertEqual(rep.skipped[0].slot, 9)

    def test_mfma_latency(self):
        # v_add reads v36/v37 written by mfma0 -> cannot sit in the immediate
        # gap after mfma0 (must respect the MFMA write->read latency window).
        src = """.text
k:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  {m} v[44:47], a[8:9], a[10:11], v[44:47]
  v_add_f32 v100, v36, v37
  s_endpgm
""".format(m=MFMA)
        ed = _editor(src)
        mfma = ed.anchors(Kind.MFMA)
        consumer = [i for i in ed.order if ed._line_of[i].opcode == "v_add_f32"][0]
        rep = ed.propose_layouts(mfma, [{0: [consumer]}])[0]
        self.assertEqual(len(rep.skipped), 1)
        self.assertEqual(rep.skipped[0].reason, SkipReason.MFMA_LATENCY)
        self.assertEqual(rep.skipped[0].bound_iid, mfma[0])

    def test_lds_roundtrip(self):
        # ds_read consumes the band filled by buffer..lds -> cannot precede it.
        src = """.text
k:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  buffer_load_dwordx4 v[4:7], v64, s[0:3], 0 offen lds
  ds_read_b128 v[20:23], v80
  s_endpgm
""".format(m=MFMA)
        ed = _editor(src)
        mfma = ed.anchors(Kind.MFMA)
        dsr = [i for i in ed.order if ed.kind_of(i) is Kind.DS_READ][0]
        load = [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD][0]
        rep = ed.propose_layouts(mfma, [{0: [dsr]}])[0]
        self.assertEqual(len(rep.skipped), 1)
        self.assertEqual(rep.skipped[0].reason, SkipReason.LDS_ROUNDTRIP)
        self.assertEqual(rep.skipped[0].bound_iid, load)

    def test_fence_blocked(self):
        # an s_mov after a barrier cannot be hoisted into a pre-barrier gap.
        src = """.text
k:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  {m} v[44:47], a[8:9], a[10:11], v[44:47]
  s_barrier
  s_mov_b32 s20, s21
  s_endpgm
""".format(m=MFMA)
        ed = _editor(src)
        mfma = ed.anchors(Kind.MFMA)
        smov = [i for i in ed.order if ed._line_of[i].opcode == "s_mov_b32"][0]
        barrier = [i for i in ed.order if ed.kind_of(i) is Kind.BARRIER][0]
        rep = ed.propose_layouts(mfma, [{0: [smov]}])[0]
        self.assertEqual(len(rep.skipped), 1)
        self.assertEqual(rep.skipped[0].reason, SkipReason.FENCE_BLOCKED)
        self.assertEqual(rep.skipped[0].bound_iid, barrier)


class TestStrictMode(unittest.TestCase):
    def test_strict_raises_on_skip(self):
        ed = _editor(_FIVE_MFMA_FOUR_LOAD)
        mfma = ed.anchors(Kind.MFMA)
        ld = _loads(ed)
        with self.assertRaises(IllegalMove):
            ed.propose_layouts(mfma, [{9: [ld[0]]}], strict=True)

    def test_strict_preserves_order(self):
        ed = _editor(_FIVE_MFMA_FOUR_LOAD)
        mfma = ed.anchors(Kind.MFMA)
        ld = _loads(ed)
        before = list(ed.order)
        try:
            ed.propose_layouts(mfma, [{9: [ld[0]]}], strict=True)
        except IllegalMove:
            pass
        self.assertEqual(ed.order, before)


if __name__ == "__main__":
    unittest.main()
