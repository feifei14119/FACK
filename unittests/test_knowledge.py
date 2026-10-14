"""M7 tests: agent/knowledge.py (skills, induction, planning) + agent/tuner.py.

Pure-CPU. The store is a throwaway temp dir per test; the tuner end-to-end test
reuses the search driver's build_candidate on the real shader (skipped if absent)
with an injected fake evaluator (no GPU)."""
import os
import shutil
import tempfile
import unittest

from agent import knowledge as kn
from agent.knowledge import Skill

SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


class TestSkillScope(unittest.TestCase):
    def test_applies_wildcard_and_match(self):
        s = Skill(id="x", statement="", when={"arch": "gfx942", "bottleneck": "memory"})
        self.assertTrue(s.applies({"arch": "gfx942", "bottleneck": "memory", "k": 1}))
        self.assertFalse(s.applies({"arch": "gfx942", "bottleneck": "compute"}))
        # empty `when` is a wildcard -> always applies
        self.assertTrue(Skill(id="y", statement="").applies({"anything": 1}))


class TestStoreIO(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="kn_test_")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def test_skill_roundtrip(self):
        s = Skill(id="s1", statement="hi", when={"arch": "gfx942"},
                  action={"specs": [{"kind": "compact"}]}, confidence=0.7,
                  status="trusted")
        kn.save_skill(s, self.store)
        loaded = kn.load_skills(self.store)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "s1")
        self.assertEqual(loaded[0].confidence, 0.7)
        self.assertEqual(loaded[0].action["specs"][0]["kind"], "compact")

    def test_log_and_read_derives_delta(self):
        kn.log_experiment({"kernel": "k", "transform": {"kind": "compact"},
                           "baseline_tflops": 100.0, "tflops": 110.0,
                           "correct": True}, self.store)
        rows = kn.read_experiments(self.store)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["delta"], 0.1)


class TestInduction(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="kn_test_")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def _log(self, kernel, transform, base, tf, correct=True, bn="memory"):
        kn.log_experiment({"kernel": kernel, "shape": "s", "arch": "gfx942",
                           "loop_kind": "mfma_dense", "bottleneck": bn,
                           "transform": transform, "baseline_tflops": base,
                           "tflops": tf, "correct": correct}, self.store)

    def test_prefer_vs_avoid_and_confidence(self):
        # a helpful transform (always +) vs a regressing one (always -)
        good = {"kind": "compact", "reorder_kind": "vmem_load", "earliest": True}
        bad = {"kind": "listsched", "weights": {"load_hoist": 1.0}}
        for k in ("kA", "kB", "kC"):
            self._log(k, good, 100.0, 120.0)
            self._log(k, bad, 100.0, 80.0)
        skills = {s.id: s for s in kn.induce_skills(self.store)}
        prefer = [s for s in skills.values() if s.action.get("specs")]
        avoid = [s for s in skills.values() if s.action.get("avoid")]
        self.assertTrue(prefer and avoid)
        self.assertGreater(prefer[0].effect["mean_delta"], 0)
        self.assertLess(avoid[0].effect["mean_delta"], 0)

    def test_trusted_gate_needs_multiple_kernels(self):
        good = {"kind": "compact", "reorder_kind": "vmem_load", "earliest": True}
        # only ONE kernel, many samples -> still candidate (anti-pollution gate)
        for _ in range(5):
            self._log("only_kernel", good, 100.0, 120.0)
        s = kn.induce_skills(self.store)[0]
        self.assertEqual(s.status, "candidate")
        # add a second + third kernel -> promotes to trusted
        self._log("k2", good, 100.0, 121.0)
        self._log("k3", good, 100.0, 119.0)
        s2 = [x for x in kn.induce_skills(self.store) if x.action.get("specs")][0]
        self.assertEqual(s2.status, "trusted")

    def test_always_incorrect_transform_is_avoid(self):
        bad = {"kind": "listsched", "weights": {"critical_path": 1.5}}
        for k in ("kA", "kB"):
            self._log(k, bad, 100.0, None, correct=False)
        s = kn.induce_skills(self.store)[0]
        self.assertTrue(s.action.get("avoid"))


class TestSeedPlan(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="kn_test_")

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def test_plan_orders_trusted_first_and_collects_avoid(self):
        kn.save_skill(Skill(
            id="cand", statement="", when={"bottleneck": "memory"},
            action={"specs": [{"kind": "compact", "reorder_kind": "ds_read",
                               "earliest": True}]}, confidence=0.4,
            status="candidate"), self.store)
        kn.save_skill(Skill(
            id="trust", statement="", when={"bottleneck": "memory"},
            action={"specs": [{"kind": "compact", "reorder_kind": "vmem_load",
                               "earliest": True}]}, confidence=0.9,
            status="trusted"), self.store)
        kn.save_skill(Skill(
            id="av", statement="", when={"bottleneck": "memory"},
            action={"avoid": ["listsched:load_hoist=1.0"]}, status="candidate"),
            self.store)
        # out-of-scope skill must be filtered out
        kn.save_skill(Skill(id="other", statement="",
                            when={"bottleneck": "compute"},
                            action={"specs": [{"kind": "ladder", "level": 0}]}),
                      self.store)

        plan = kn.seed_search_plan({"arch": "gfx942", "bottleneck": "memory"},
                                   self.store)
        self.assertEqual(plan["specs"][0]["reorder_kind"], "vmem_load")  # trusted first
        self.assertEqual(plan["specs"][1]["reorder_kind"], "ds_read")
        self.assertIn("listsched:load_hoist=1.0", plan["avoid"])
        self.assertNotIn("other", plan["skills_used"])

    def test_plan_surfaces_quant_constraints_and_conflicts(self):
        # a gold-mined quant skill must flow its fine-grained constraints +
        # conflict_groups through the plan (so they reach Observation.prior_plan).
        kn.save_skill(Skill(
            id="gold-mfma_dense-loop-quant", statement="",
            when={"arch": "gfx942", "loop_kind": "mfma_dense", "region": "loop"},
            action={"constraints": [
                        {"metric": "mfma_gap_size",
                         "stat": {"median": 2.0, "max": 4.0}, "weight": 0.9},
                        {"metric": "per_slot_capacity", "kind": "ds_read",
                         "stat": {"median": 2.0, "max": 2.0}, "weight": 0.8},
                        {"metric": "adjacent_cooccur", "kind": "ds_read",
                         "value": 0.1, "polarity": "avoid", "weight": 0.7}],
                    "conflict_groups": [["per_slot_capacity:ds_read",
                                         "adjacent_cooccur:ds_read"]]},
            confidence=0.85, status="candidate"), self.store)

        ctx = {"arch": "gfx942", "loop_kind": "mfma_dense", "region": "loop"}
        plan = kn.seed_search_plan(ctx, self.store)
        metrics = {(c["metric"], c.get("kind")) for c in plan["constraints"]}
        self.assertIn(("mfma_gap_size", None), metrics)
        self.assertIn(("per_slot_capacity", "ds_read"), metrics)
        self.assertEqual(plan["conflict_groups"],
                         [["per_slot_capacity:ds_read", "adjacent_cooccur:ds_read"]])

    def test_plan_constraints_empty_without_quant_skills(self):
        kn.save_skill(Skill(
            id="c", statement="", when={"region": "loop"},
            action={"specs": [{"kind": "ladder", "level": 0}]}), self.store)
        plan = kn.seed_search_plan({"region": "loop"}, self.store)
        self.assertEqual(plan["constraints"], [])
        self.assertEqual(plan["conflict_groups"], [])


class _FakeEval:
    def __init__(self, base=100.0, bonus_substr="compact", bonus=50.0):
        self.base, self.bonus_substr, self.bonus = base, bonus_substr, bonus

    def evaluate(self, s_path, with_counters=False):
        name = os.path.basename(s_path)
        tf = self.base + (self.bonus if self.bonus_substr in name else 0.0)
        d = {"bottleneck": "memory"} if with_counters else None
        return type("R", (), {"compiled": True, "correct": True, "tflops": tf, "direction": d})()


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestTunerEndToEnd(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="kn_test_")
        self.seed = open(SHADER).read()

    def tearDown(self):
        shutil.rmtree(self.store, ignore_errors=True)

    def test_tune_seeds_plan_and_learns(self):
        from agent import tuner
        # seed a prior so extra_specs is non-empty
        kn.save_skill(Skill(
            id="prior", statement="", when={"bottleneck": "memory"},
            action={"specs": [{"kind": "compact", "reorder_kind": "vmem_load",
                               "earliest": True}]}, confidence=0.8,
            status="trusted"), self.store)
        ctx = {"arch": "gfx942", "loop_kind": "mfma_dense", "bottleneck": "memory",
               "kernel": "fp8gemm", "shape": "k4096", "scenario": "hand_tuned"}
        res, plan = tuner.tune(self.seed, _FakeEval(), ctx, store=self.store,
                               perf_repeats=1, direction_captures=3)
        self.assertTrue(plan["specs"])                 # prior was injected
        self.assertGreater(res.best_tflops, res.baseline_tflops)
        # learning happened: experiments logged + skills induced/saved
        self.assertTrue(kn.read_experiments(self.store))
        self.assertTrue(kn.load_skills(self.store))


if __name__ == "__main__":
    unittest.main()
