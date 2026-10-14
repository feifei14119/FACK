"""Mixed core-loop support (proj/mixed_loop_scheduling.md P0): loop detection
with cold-path re-entry / outlined code, join-label fences, hot-loop selection,
loop-exit waitcnt guard."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions, waitcnt
from reorder.editor import RegionEditor
from reorder.model import LineKind
from reorder.verifier import Verifier

MFMA = "  v_mfma_f32_32x32x8_f16 v[0:15], v[16:17], v[18:19], v[0:15]\n"

# setup loop (no MFMA) -> core loop whose cold tail lives after s_endpgm and
# jumps back into the MIDDLE of the body -> epilogue with a conditional join.
MIXED_STYLE = (
    ".text\nk:\n"
    "  s_mov_b32 s10, 4\n"
    "setup:\n"
    "  s_sub_u32 s10, s10, 1\n"
    "  s_cmp_eq_u32 s10, 0\n"
    "  s_cbranch_scc0 setup\n"
    "  s_mov_b32 s11, 8\n"
    "core:\n"
    + MFMA +
    "  s_cmp_eq_u32 s12, 0\n"
    "  s_cbranch_scc1 tail\n"
    "rejoin:\n"
    + MFMA +
    "  s_sub_u32 s11, s11, 1\n"
    "  s_cmp_lg_u32 s11, 0\n"
    "  s_cbranch_scc1 core\n"
    "  s_cmp_eq_u32 s13, 0\n"
    "  s_cbranch_scc1 join\n"
    "  v_mov_b32 v30, 1.0\n"
    "  global_store_dword v[20:21], v30, off\n"
    "join:\n"
    "  v_add_f32 v31, v32, v33\n"
    "  v_add_f32 v34, v35, v36\n"
    "  s_endpgm\n"
    "tail:\n"
    "  v_mov_b32 v40, 0\n"
    "  s_branch rejoin\n")


def _load(src):
    prog = parser.parse(src)
    return prog, Gfx942Target.from_program(prog)


def _line(prog, text):
    return next(ln for ln in prog.lines
                if ln.kind is LineKind.INSTR and ln.raw.strip().startswith(text))


def _label(prog, name):
    return next(ln.idx for ln in prog.lines if ln.label == name)


class TestLoopDetection(unittest.TestCase):
    def test_cold_reentry_is_not_a_back_edge(self):
        prog, t = _load(MIXED_STYLE)
        a = regions.analyze(prog, t)
        self.assertEqual([lp.header_label for lp in a.loops], ["setup", "core"])
        core = next(lp for lp in a.loops if lp.header_label == "core")
        self.assertEqual(core.line_end, _line(prog, "s_cbranch_scc1 core").idx)

    def test_region_kinds(self):
        prog, t = _load(MIXED_STYLE)
        a = regions.analyze(prog, t)
        self.assertEqual([r.kind.value for r in a.regions],
                         ["prologue", "loop", "inter", "loop", "epilogue", "outlined"])
        outl = a.regions[-1]
        self.assertTrue(outl.outlined)
        self.assertEqual(outl.line_start, _label(prog, "tail"))
        epi = a.regions[-2]
        self.assertEqual(epi.line_end, _line(prog, "s_endpgm").idx)

    def test_rotated_loop_still_detected(self):
        src = (".text\nk:\n"
               "  s_mov_b32 s0, 4\n"
               "  s_branch check\n"
               "top:\n" + MFMA +
               "  s_sub_u32 s0, s0, 1\n"
               "check:\n"
               "  s_cmp_lg_u32 s0, 0\n"
               "  s_cbranch_scc1 top\n"
               "  s_endpgm\n")
        prog, t = _load(src)
        a = regions.analyze(prog, t)
        self.assertEqual([lp.header_label for lp in a.loops], ["top"])
        self.assertIsNone(a.outline_start)

    def test_early_exit_endpgm_does_not_outline(self):
        src = (".text\nk:\n"
               "  s_cmp_eq_u32 s0, 0\n"
               "  s_cbranch_scc0 go\n"
               "  s_endpgm\n"
               "go:\n" + MFMA +
               "  s_sub_u32 s1, s1, 1\n"
               "  s_cmp_lg_u32 s1, 0\n"
               "  s_cbranch_scc1 go\n"
               "  s_endpgm\n"
               "  s_code_end\n")
        prog, t = _load(src)
        a = regions.analyze(prog, t)
        self.assertIsNone(a.outline_start)
        self.assertEqual([r.kind.value for r in a.regions], ["prologue", "loop", "epilogue"])

    def test_main_loop_placed_after_endpgm(self):
        # exits jump back to an earlier epilogue label: not back-edges
        src = (".text\nk:\n"
               "  s_branch lp\n"
               "done:\n"
               "  v_add_f32 v1, v2, v3\n"
               "  s_endpgm\n"
               "lp:\n" + MFMA +
               "  s_sub_u32 s1, s1, 1\n"
               "  s_cmp_eq_u32 s1, 0\n"
               "  s_cbranch_scc1 done\n"
               "  s_branch lp\n")
        prog, t = _load(src)
        a = regions.analyze(prog, t)
        self.assertEqual([lp.header_label for lp in a.loops], ["lp"])
        self.assertEqual([r.kind.value for r in a.regions], ["prologue", "loop"])
        self.assertIs(regions.select_region(a.regions, "loop", prog, t), a.regions[1])


class TestSelectRegion(unittest.TestCase):
    def setUp(self):
        self.prog, self.t = _load(MIXED_STYLE)
        self.regs = regions.analyze(self.prog, self.t).regions

    def test_hot_loop_default(self):
        r = regions.select_region(self.regs, "loop", self.prog, self.t)
        self.assertEqual(r.header_label, "core")

    def test_legacy_without_program(self):
        self.assertEqual(regions.select_region(self.regs, "loop").header_label, "setup")
        self.assertEqual(regions.select_region(self.regs, "loop#1").header_label, "core")

    def test_by_label(self):
        self.assertEqual(regions.select_region(self.regs, "loop@core").header_label, "core")
        with self.assertRaises(ValueError):
            regions.select_region(self.regs, "loop@nope")

    def test_outlined(self):
        self.assertTrue(regions.select_region(self.regs, "outlined").outlined)


class TestJoinFence(unittest.TestCase):
    def test_conditional_store_cannot_sink_past_join(self):
        prog, t = _load(MIXED_STYLE)
        a = regions.analyze(prog, t)
        epi = regions.select_region(a.regions, "epilogue")
        ed = RegionEditor(prog, t, epi, treat_waitcnt_as_fence=False)
        store = _line(prog, "global_store_dword").idx
        first_after_join = _line(prog, "v_add_f32 v31").idx
        self.assertIn(first_after_join, ed._fences)
        lo, hi, order_wo = ed._block_insert_range(ed.unit(store))
        self.assertLessEqual(hi, order_wo.index(first_after_join))
        # and nothing after the join can be hoisted above it
        later = _line(prog, "v_add_f32 v34").idx
        lo, hi, order_wo = ed._block_insert_range(ed.unit(later))
        self.assertGreater(lo, order_wo.index(first_after_join))


class TestLoopExitGuard(unittest.TestCase):
    def test_live_out_load_stays_synced(self):
        # the only consumer of s20 is after the loop; the in-loop wait is
        # dropped by the loop pass, so the guard must sync the exit
        src = (".text\nk:\n"
               "lp:\n"
               "  s_load_dword s20, s[8:9], 0x0\n"
               "  s_waitcnt lgkmcnt(0)\n"
               "  s_add_u32 s21, s21, 1\n"
               "  s_cmp_lg_u32 s21, 8\n"
               "  s_cbranch_scc1 lp\n"
               "  s_add_u32 s22, s20, 1\n"
               "  s_endpgm\n")
        prog, t = _load(src)
        ref = parser.parse(src)
        a = regions.analyze(prog, t)
        loop = regions.select_region(a.regions, "loop")
        waitcnt.recompute(prog, t, region=loop)
        res = Verifier(t, reference=ref, analysis=regions.analyze(prog, t)).verify(prog)
        self.assertTrue(res.ok, res.violations)
        instr = [ln.raw.strip() for ln in prog.lines if ln.kind is LineKind.INSTR]
        k = instr.index("s_add_u32 s22, s20, 1")
        self.assertTrue(any(x.startswith("s_waitcnt") and "lgkmcnt(0)" in x
                            for x in instr[instr.index("s_cbranch_scc1 lp") + 1:k]), instr)

    def test_unchanged_loop_leaves_epilogue_alone(self):
        src = (".text\nk:\n"
               "lp:\n"
               "  s_load_dword s20, s[8:9], 0x0\n"
               "  s_waitcnt lgkmcnt(0)\n"
               "  s_add_u32 s21, s20, 1\n"
               "  s_cmp_lg_u32 s21, 8\n"
               "  s_cbranch_scc1 lp\n"
               "  s_add_u32 s22, s20, 1\n"
               "  s_endpgm\n")
        prog, t = _load(src)
        loop = regions.select_region(regions.analyze(prog, t).regions, "loop")
        waitcnt.recompute(prog, t, region=loop)
        instr = [ln.raw.strip() for ln in prog.lines if ln.kind is LineKind.INSTR]
        k = instr.index("s_add_u32 s22, s20, 1")
        self.assertEqual(instr[k - 1], "s_cbranch_scc1 lp")


class TestPhases(unittest.TestCase):
    def test_split(self):
        from reorder import phases
        # 4 anchors with small gaps, a 30-long gap, then 3 anchors
        order = list(range(60))
        anchors = [0, 2, 4, 6, 37, 39, 41]
        ph = phases.split_phases(order, anchors)
        self.assertEqual([(p.kind, p.lo, p.hi) for p in ph],
                         [("anchored", 0, 6), ("anchorless", 7, 36), ("anchored", 37, 59)])
        self.assertEqual(ph[2].anchors, [37, 39, 41])

    def test_prefix_suffix_and_no_anchor(self):
        from reorder import phases
        order = list(range(100))
        ph = phases.split_phases(order, [40, 42, 44])
        self.assertEqual([(p.kind, p.lo, p.hi) for p in ph],
                         [("anchorless", 0, 39), ("anchored", 40, 44), ("anchorless", 45, 99)])
        self.assertEqual([(p.kind, p.lo, p.hi) for p in phases.split_phases(order, [])],
                         [("anchorless", 0, 99)])

    def test_plain_gemm_loop_is_one_phase(self):
        from reorder import phases
        order = list(range(50))
        ph = phases.split_phases(order, list(range(0, 50, 5)))
        self.assertEqual(len(ph), 1)
        self.assertEqual(ph[0].kind, "anchored")


def _mixed_loop_src():
    """GEMM (4 MFMA) -> 30 independent VALUs -> GEMM (4 MFMA), in one loop."""
    body = MFMA * 4
    body += "".join("  v_add_f32 v{}, v{}, v{}\n".format(100 + k, 200 + k, 230 + k)
                    for k in range(30))
    body += MFMA * 4
    return (".text\nk:\n  s_mov_b32 s11, 8\nlp:\n" + body +
            "  s_sub_u32 s11, s11, 1\n  s_cmp_lg_u32 s11, 0\n  s_cbranch_scc1 lp\n"
            "  s_endpgm\n")


class TestMixedObserve(unittest.TestCase):
    def test_phase_views(self):
        from agent.session import AgentSession
        sess = AgentSession(_mixed_loop_src(), None)
        obs = sess.observe(with_direction=False)
        self.assertIsNone(obs.dag)                      # region has anchors
        kinds = [p["kind"] for p in obs.phases]
        self.assertEqual(kinds, ["anchored", "anchorless", "anchored"])
        mid = obs.phases[1]
        self.assertEqual(mid["size"], 30)
        self.assertEqual(mid["replaces_slot"], 3)
        self.assertEqual(len(mid["dag"]), 30)
        self.assertIn("segments", mid)
        self.assertEqual(obs.phases[0]["slots"], [0, 1, 2])
        self.assertIn("phases", obs.to_dict())

    def test_anchorless_region_keeps_top_level_view(self):
        from agent.session import AgentSession
        src = (".text\nk:\n" + "".join("  v_add_f32 v{}, v1, v2\n".format(10 + k)
                                       for k in range(5)) + "  s_endpgm\n")
        obs = AgentSession(src, None, region="body").observe(with_direction=False)
        self.assertIsNotNone(obs.dag)
        self.assertEqual(len(obs.phases), 1)
        self.assertNotIn("dag", obs.phases[0])

    def test_phase_listsched_touches_only_that_phase(self):
        from search.list_scheduler import Weights, schedule_phase
        prog, t = _load(_mixed_loop_src())
        loop = regions.select_region(regions.analyze(prog, t).regions, "loop", prog, t)
        ed = RegionEditor(prog, t, loop, treat_waitcnt_as_fence=False)
        base = list(ed.order)
        new = schedule_phase(ed, Weights(critical_path=0.0, latency=0.0,
                                         order_tiebreak=-1.0), phase=1)
        self.assertEqual(sorted(new), sorted(base))
        self.assertEqual(new[:4], base[:4])
        self.assertEqual(new[34:], base[34:])
        self.assertNotEqual(new[4:34], base[4:34])
        self.assertTrue(ed.graph.is_order_legal(new, fences=ed._fences))

    def test_cross_phase_migration(self):
        from agent.session import AgentSession
        # v40 <- v0 reads GEMM1's result and is overwritten by GEMM2 (pinned);
        # v16 clobbers both GEMMs' A operand (pinned); v42 <- v40 can only
        # sink; the 30 independent adds go either way
        src = _mixed_loop_src().replace(
            MFMA * 4 + "  v_add_f32", MFMA * 4 + "  v_mov_b32 v40, v0\n"
            "  v_mov_b32 v16, v41\n  v_mov_b32 v42, v40\n  v_add_f32", 1)
        sess = AgentSession(src, None)
        obs = sess.observe(with_direction=False)
        self.assertEqual([p["kind"] for p in obs.phases],
                         ["anchored", "anchorless", "anchored"])
        mig = obs.phases[1]["migration"]
        line_of = sess._editor()._line_of
        ops = {i: ln.opcode for i, ln in line_of.items()}
        reads_acc = next(i for i in ops if ops[i] == "v_mov_b32"
                         and "v0" in line_of[i].operands)
        clobber = next(i for i in ops if ops[i] == "v_mov_b32"
                       and line_of[i].operands[0] == "v16")
        chained = next(i for i in ops if ops[i] == "v_mov_b32"
                       and line_of[i].operands[0] == "v42")
        to_prev = {x["iid"]: x["slots"] for x in mig["to_prev"]}
        to_next = {x["iid"]: x["slots"] for x in mig["to_next"]}
        for pinned in (reads_acc, clobber):
            self.assertNotIn(pinned, to_prev)
            self.assertNotIn(pinned, to_next)
        self.assertNotIn(chained, to_prev)
        self.assertIn(chained, to_next)
        self.assertEqual(len(to_prev), 30)
        self.assertEqual(len(to_next), 31)
        add = next(i for i in to_next if ops[i] == "v_add_f32")
        self.assertEqual(to_prev[add], [0, 1, 2])
        self.assertEqual(to_next[add], [4, 5, 6])
        rep = sess.propose([{5: [add]}, {1: [reads_acc]}])
        self.assertEqual(len(rep[0].placed), 1)
        self.assertEqual(len(rep[1].placed), 0)



if __name__ == "__main__":
    unittest.main()
