"""M3 tests: pure reorder engine (RegionEditor) on synthetic programs,
a cold-start fixture, AND the real testcase/ kernel."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions, emitter
from reorder.editor import RegionEditor, IllegalMove
from reorder.model import Kind, LineKind

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _editor(src, region_kind=None, **kw):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    a = regions.analyze(prog, t)
    if region_kind is None:
        reg = a.regions[0]
    else:
        reg = [r for r in a.regions if r.kind.value == region_kind][0]
    return prog, t, RegionEditor(prog, t, reg, **kw)


class TestColdStartDistribute(unittest.TestCase):
    def setUp(self):
        self.src = _read(os.path.join(FIX, "coldstart_mfma.s"))

    def test_distribute_interleaves(self):
        prog, t, ed = _editor(self.src)
        mfma = ed.anchors(Kind.MFMA)
        d = ed.distribute_evenly(Kind.DS_READ, 0, len(mfma) - 1)
        self.assertTrue(d.changed)
        self.assertEqual(d.skipped, [])
        kinds = [ed.kind_of(i).value for i in ed.order]
        # expect mfma/ds alternating across the 5 MFMA / 4 ds_read
        self.assertEqual(kinds,
                         ["mfma", "ds_read"] * 4 + ["mfma", "branch"])
        self.assertTrue(ed.is_legal())

    def test_distribute_reversible(self):
        prog, t, ed = _editor(self.src)
        before = list(ed.order)
        d = ed.distribute_evenly(Kind.DS_READ, 0, len(ed.anchors(Kind.MFMA)) - 1)
        self.assertNotEqual(ed.order, before)
        ed.revert(d)
        self.assertEqual(ed.order, before)

    def test_materialize_after_distribute(self):
        prog, t, ed = _editor(self.src)
        ed.distribute_evenly(Kind.DS_READ, 0, len(ed.anchors(Kind.MFMA)) - 1)
        ed.materialize()
        out = emitter.emit(prog)
        # same number of lines/instructions, but order changed
        reparsed = parser.parse(out)
        self.assertEqual(reparsed.count(LineKind.INSTR), prog.count(LineKind.INSTR))
        self.assertNotEqual(out, self.src)


class TestLowLevelPrimitives(unittest.TestCase):
    def setUp(self):
        self.src = _read(os.path.join(FIX, "coldstart_mfma.s"))

    def _ds(self, ed):
        return [i for i in ed.order if ed.kind_of(i) is Kind.DS_READ]

    def test_move_after_legal(self):
        prog, t, ed = _editor(self.src)
        mfma = ed.anchors(Kind.MFMA)
        ds = self._ds(ed)
        d = ed.move_after(ds[0], mfma[0])
        self.assertTrue(d.changed)
        self.assertTrue(ed.is_legal())
        # ds[0] now immediately after mfma[0]
        self.assertEqual(ed.order[ed.order.index(mfma[0]) + 1], ds[0])

    def test_illegal_move_strict_raises(self):
        # moving the first MFMA after the third breaks the ACC chain
        prog, t, ed = _editor(self.src)
        mfma = ed.anchors(Kind.MFMA)
        with self.assertRaises(IllegalMove):
            ed.move_after(mfma[0], mfma[2], strict=True)

    def test_illegal_move_nonstrict_skips(self):
        prog, t, ed = _editor(self.src)
        mfma = ed.anchors(Kind.MFMA)
        before = list(ed.order)
        d = ed.move_after(mfma[0], mfma[2], strict=False)
        self.assertFalse(d.changed)
        self.assertIn(mfma[0], d.skipped)
        self.assertEqual(ed.order, before)

    def test_cannot_move_fence(self):
        prog, t, ed = _editor(self.src)
        endpgm = [i for i in ed.order if ed.kind_of(i) is Kind.BRANCH][0]
        d = ed.move_before(endpgm, ed.order[0], strict=False)
        self.assertFalse(d.changed)

    def test_swap_independent(self):
        prog, t, ed = _editor(self.src)
        ds = self._ds(ed)
        d = ed.swap(ds[0], ds[2])
        self.assertTrue(d.changed)
        self.assertTrue(ed.is_legal())


class TestBundleIntegrity(unittest.TestCase):
    def test_m0_bundle_moves_together(self):
        src = (".text\nk:\n"
               "  s_add_u32 m0, 0, s58\n"
               "  buffer_load_dword v30, s[4:7], 0 offen lds\n"
               "  v_add_f32 v10, v11, v12\n"
               "  v_add_f32 v13, v14, v15\n"
               "  s_endpgm\n")
        prog, t, ed = _editor(src)
        setter = [i for i in ed.order if "m0" in ed.graph.by_iid[i].defs][0]
        load = [i for i in ed.order if (ed.graph.by_iid[i].line.opcode or "")
                .startswith("buffer_load")][0]
        # the load's unit is the m0 bundle [setter, load]
        self.assertEqual(set(ed.unit(load)), {setter, load})
        vadds = [i for i in ed.order if ed.kind_of(i) is Kind.VALU]
        d = ed.move_after(load, vadds[1])
        self.assertTrue(d.changed)
        # setter and load remain contiguous (bundle preserved)
        si, li = ed.order.index(setter), ed.order.index(load)
        self.assertEqual(li, si + 1)
        self.assertTrue(ed.is_legal())

    def test_lock_bundle_glues_group(self):
        src = (".text\nk:\n"
               "  v_add_f32 v1, v2, v3\n"
               "  v_add_f32 v4, v5, v6\n"
               "  v_add_f32 v7, v8, v9\n"
               "  s_endpgm\n")
        prog, t, ed = _editor(src)
        a, b = ed.order[0], ed.order[1]
        ed.lock_bundle([a, b])
        self.assertEqual(set(ed.unit(a)), {a, b})


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestRealKernelEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = _read(SHADER)

    def test_unedited_materialize_lossless(self):
        prog, t, ed = _editor(self.src, "loop")
        self.assertEqual(emitter.emit(ed.materialize()), self.src)

    def test_distribute_is_safe_and_reversible(self):
        # even if the hand-scheduled kernel pins ds_read (skips), it must stay
        # legal and be perfectly reversible.
        prog, t, ed = _editor(self.src, "loop", treat_waitcnt_as_fence=False)
        before = list(ed.order)
        d = ed.distribute_evenly(Kind.DS_READ, 0, len(ed.anchors(Kind.MFMA)) - 1)
        self.assertTrue(ed.is_legal())
        ed.revert(d)
        self.assertEqual(ed.order, before)

    def test_real_within_window_move(self):
        # some instruction in the loop can still be relocated within its window
        prog, t, ed = _editor(self.src, "loop", treat_waitcnt_as_fence=False)
        moved = False
        for f in list(ed.order):
            if ed.kind_of(f) in (Kind.BRANCH, Kind.BARRIER):
                continue
            lo, hi, order_wo = ed._block_insert_range([f])
            cur_wo = len(order_wo) if not order_wo else \
                len([x for x in ed.order[:ed.order.index(f)]])
            if hi > lo:  # window has room to move
                target = hi if hi != cur_wo else lo
                anchor = order_wo[target - 1] if target > 0 else None
                if anchor is not None:
                    d = ed.move_after(f, anchor, strict=False)
                    if d.changed:
                        self.assertTrue(ed.is_legal())
                        moved = True
                        break
        self.assertTrue(moved, "expected at least one legal within-window move")

    def test_materialize_after_edit_reparses(self):
        prog, t, ed = _editor(self.src, "loop", treat_waitcnt_as_fence=False)
        # do a guaranteed-legal swap of two adjacent independent instrs if any
        ds = [i for i in ed.order if ed.kind_of(i) is Kind.DS_READ]
        ed.move_after(ds[0], ed.order[ed.order.index(ds[0]) + 1], strict=False)
        ed.materialize()
        out = emitter.emit(prog)
        reparsed = parser.parse(out)
        self.assertEqual(reparsed.count(LineKind.INSTR), prog.count(LineKind.INSTR))


def _big_indep_src(n):
    """n mutually-independent v_add (distinct dest/src regs) -> a fully-movable
    anchor-less region, so a full linear order is always legal + placeable."""
    lines = [".text", "k:"]
    for i in range(n):
        lines.append("  v_add_u32 v%d, v%d, v%d" % (i, 200 + i, 400 + i))
    lines.append("  s_endpgm")
    return "\n".join(lines) + "\n"


class TestProposeOrdersScaling(unittest.TestCase):
    """anchorless_fullorder_propose_perf.md direction B: the O(1) position cache
    keeps propose_orders fast + correct on a large full order."""

    def _editor_big(self, n):
        prog = parser.parse(_big_indep_src(n))
        t = Gfx942Target.from_program(prog)
        reg = regions.analyze(prog, t).regions[0]
        return RegionEditor(prog, t, reg, treat_waitcnt_as_fence=False)

    def test_full_order_all_placed(self):
        ed = self._editor_big(120)
        order = list(ed.order)
        rep = ed.propose_orders([order])[0]
        self.assertTrue(rep.legal)
        self.assertFalse(rep.skipped)
        self.assertEqual(len(rep.placed), len(order))
        self.assertEqual(ed.order, order)                 # non-committing

    def test_reversed_order_legal_and_noncommitting(self):
        ed = self._editor_big(80)
        base = list(ed.order)
        rep = ed.propose_orders([list(reversed(base))])[0]
        self.assertTrue(rep.legal)                         # independent -> any perm legal
        self.assertEqual(ed.order, base)                   # seed untouched

    def test_large_full_order_is_fast(self):
        import time
        ed = self._editor_big(300)
        order = list(ed.order)
        t0 = time.time()
        ed.propose_orders([order])
        self.assertLess(time.time() - t0, 3.0)             # was minutes at n~400

    def test_max_intent_guard_rejects(self):
        ed = self._editor_big(100)
        rep = ed.propose_orders([list(ed.order)], max_intent=50)[0]
        self.assertFalse(rep.legal)
        self.assertIsNotNone(rep.error)
        self.assertFalse(rep.placed)


if __name__ == "__main__":
    unittest.main()
