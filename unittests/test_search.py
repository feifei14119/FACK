"""M6c tests: search layer (movedsl / list_scheduler / driver).

Pure-CPU: movedsl + list_scheduler run on synthetic programs; the driver's
build_candidate runs the real engine on the testcase shader; search() is driven
by an injected FakeEvaluator (no GPU)."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.editor import RegionEditor
from reorder.model import Kind
from search import movedsl
from search.list_scheduler import Weights, schedule
from search import driver

MFMA = "v_mfma_f32_16x16x32_fp8_fp8"
SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")

_SYNTH = """.text
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


def _editor(src):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    reg = regions.analyze(prog, t).regions[0]
    return RegionEditor(prog, t, reg, treat_waitcnt_as_fence=False)


class TestMoveDSL(unittest.TestCase):
    def setUp(self):
        self.ed = _editor(_SYNTH)

    def test_resolve_kind_index(self):
        self.assertIs(self.ed.kind_of(movedsl.resolve(self.ed, "mfma#0")), Kind.MFMA)
        self.assertIs(self.ed.kind_of(movedsl.resolve(self.ed, "vmem_load#1")),
                      Kind.VMEM_LOAD)

    def test_resolve_semantic_anchor(self):
        # the load whose operands mention v64
        iid = movedsl.resolve(self.ed, "vmem_load@v64")
        self.assertIn("v64", " ".join(self.ed._line_of[iid].operands))

    def test_resolve_raw_iid(self):
        any_iid = self.ed.order[0]
        self.assertEqual(movedsl.resolve(self.ed, "#%d" % any_iid), any_iid)

    def test_resolve_errors_nonstrict(self):
        res = movedsl.apply_moves(self.ed, [{"op": "hoist", "target": "ds_read#9",
                                             "after": "mfma#0"}], strict=False)
        self.assertFalse(res[0].ok)

    def test_heterogeneous_layout_via_dsl(self):
        loads = [i for i in self.ed.order if self.ed.kind_of(i) is Kind.VMEM_LOAD]
        moves = [{"op": "layout", "slots": {0: [loads[0], loads[1]], 2: [loads[2]]}}]
        log = movedsl.apply_moves(self.ed, moves)
        self.assertTrue(log[0].ok)
        kinds = [self.ed.kind_of(i).value for i in self.ed.order]
        self.assertEqual(kinds[:4], ["mfma", "vmem_load", "vmem_load", "mfma"])
        self.assertTrue(self.ed.is_legal())

    def test_hoist_list_after_anchor(self):
        loads = [i for i in self.ed.order if self.ed.kind_of(i) is Kind.VMEM_LOAD]
        moves = [{"op": "hoist", "target": [loads[0], loads[1]], "after": "mfma#0"}]
        log = movedsl.apply_moves(self.ed, moves)
        self.assertTrue(log[0].ok)
        mfma0 = movedsl.resolve(self.ed, "mfma#0")
        self.assertEqual(self.ed.order[self.ed.order.index(mfma0) + 1], loads[0])
        self.assertEqual(self.ed.order[self.ed.order.index(mfma0) + 2], loads[1])


class TestListScheduler(unittest.TestCase):
    def setUp(self):
        self.ed = _editor(_SYNTH)

    def test_schedule_is_legal_permutation(self):
        new = schedule(self.ed.graph, self.ed.order, self.ed._fences,
                       Weights(), kind_of=self.ed.kind_of)
        self.assertEqual(set(new), set(self.ed.order))
        self.assertEqual(len(new), len(self.ed.order))
        self.assertTrue(self.ed.graph.is_order_legal(new, fences=self.ed._fences))

    def test_load_hoist_weight_moves_loads_early(self):
        new = schedule(self.ed.graph, self.ed.order, self.ed._fences,
                       Weights(load_hoist=10.0), kind_of=self.ed.kind_of)
        first_load = next(k for k, i in enumerate(new)
                          if self.ed.kind_of(i) is Kind.VMEM_LOAD)
        # loads (originally after all MFMAs) get scheduled at the very front
        self.assertEqual(first_load, 0)
        self.assertTrue(self.ed.graph.is_order_legal(new, fences=self.ed._fences))

    def test_fence_pinned(self):
        # branch/endpgm is a fence and must remain last
        new = schedule(self.ed.graph, self.ed.order, self.ed._fences,
                       Weights(load_hoist=10.0), kind_of=self.ed.kind_of)
        endpgm = [i for i in self.ed.order if self.ed.kind_of(i) is Kind.BRANCH]
        if endpgm:
            self.assertEqual(new[-1], endpgm[0])


class TestDirectionVote(unittest.TestCase):
    def test_trusted_logic(self):
        self.assertTrue(driver.DirectionVote("memory", 0.8).trusted())
        self.assertFalse(driver.DirectionVote("memory", 0.4).trusted())
        self.assertFalse(driver.DirectionVote("latency", 1.0).trusted())
        self.assertFalse(driver.DirectionVote("none", 1.0).trusted())

    def test_vote_aggregates(self):
        seq = ["memory", "memory", "compute", "memory", "lds"]

        class FakeEv:
            def __init__(self):
                self.i = 0

            def evaluate(self, s_path, with_counters=False):
                b = seq[self.i % len(seq)]
                self.i += 1
                return type("R", (), {"correct": True, "tflops": 1.0,
                                      "direction": {"bottleneck": b}})()

        v = driver.vote_direction(FakeEv(), "x.s", n=5)
        self.assertEqual(v.bottleneck, "memory")
        self.assertEqual(v.votes["memory"], 3)
        self.assertAlmostEqual(v.confidence, 0.6)


class _FakeEval:
    """Filename-scored fake evaluator (no GPU). tflops keyed off the candidate
    name in the path; optionally marks a family incorrect."""

    def __init__(self, base=100.0, bonus_substr=None, bonus=50.0,
                 wrong_substr=None, direction="memory"):
        self.base = base
        self.bonus_substr = bonus_substr
        self.bonus = bonus
        self.wrong_substr = wrong_substr
        self.direction = direction

    def evaluate(self, s_path, with_counters=False):
        name = os.path.basename(s_path)
        correct = not (self.wrong_substr and self.wrong_substr in name)
        tflops = self.base + (self.bonus if (self.bonus_substr
                                             and self.bonus_substr in name) else 0.0)
        d = {"bottleneck": self.direction} if with_counters else None
        return type("R", (), {"compiled": True, "correct": correct, "tflops": tflops, "direction": d})()


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestDriverBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = open(SHADER).read()

    def test_build_ladder_and_compact(self):
        for spec in ({"kind": "ladder", "level": 1},
                     {"kind": "compact", "reorder_kind": "vmem_load", "earliest": True}):
            text, ok = driver.build_candidate(self.seed, spec)
            self.assertTrue(ok, spec)
            self.assertIn(".text", text)

    def test_build_listsched_legal_or_rejected(self):
        text, ok = driver.build_candidate(
            self.seed, {"kind": "listsched", "weights": Weights(load_hoist=1.0)})
        # either it produced a legal verified schedule, or was cleanly rejected
        self.assertIn(ok, (True, False))
        if ok:
            self.assertIn(".text", text)


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestSearchLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = open(SHADER).read()

    def test_correctness_gating_keeps_baseline(self):
        # every non-baseline candidate is faster but INCORRECT -> never accepted
        ev = _FakeEval(base=100.0, bonus_substr="compact", bonus=900.0,
                       wrong_substr="compact")
        res = driver.search(self.seed, ev, perf_repeats=1, direction_captures=3)
        self.assertEqual(res.best_name, "baseline")
        self.assertEqual(res.best_tflops, 100.0)

    def test_accepts_faster_correct_candidate(self):
        ev = _FakeEval(base=100.0, bonus_substr="compact", bonus=50.0,
                       direction="memory")
        res = driver.search(self.seed, ev, perf_repeats=1, direction_captures=3,
                            noise_margin=0.0)
        self.assertGreater(res.best_tflops, res.baseline_tflops)
        self.assertIn("compact", res.best_name)
        # a memory-trusted vote should have prioritised vmem_load operators
        self.assertTrue(res.direction.trusted())

    def test_low_confidence_uses_fallback(self):
        # diffuse 'latency' vote -> not trusted -> fallback specs still run
        ev = _FakeEval(base=100.0, bonus_substr="listsched", bonus=30.0,
                       direction="latency")
        res = driver.search(self.seed, ev, perf_repeats=1, direction_captures=3)
        self.assertFalse(res.direction.trusted())
        self.assertGreaterEqual(len(res.trials), 2)  # baseline + fallback candidates


if __name__ == "__main__":
    unittest.main()
