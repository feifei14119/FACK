"""M7 LLM decision-surface tests: AgentSession.observe / propose / commit_and_eval.

observe is the read-only facts map; propose is non-committing with SkipReason
feedback; commit_and_eval runs the gated build->eval path on an injected fake
evaluator (no GPU). Asserts the LLM-driven layout flows through the SAME
correctness/Verifier/noise gate as every other candidate."""
import os
import tempfile
import unittest

from agent.session import AgentSession
from reorder import parser, regions
from reorder.editor import RegionEditor, SkipReason
from reorder.model import Kind
from isa.gfx942.target import Gfx942Target

SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")

MFMA = "v_mfma_f32_16x16x32_fp8_fp8"
# 5 MFMA + 4 independent loads, all clustered (a cold layout): each load has a
# wide window over the MFMA gaps, so per-slot layouts are exercisable on CPU.
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


class _FakeEval:
    """Filename-scored fake evaluator. Layout candidates ('agent_layout') score
    higher so commit_and_eval accepts them; baseline scores lower."""

    def __init__(self, base=100.0, layout_bonus=20.0, wrong=False, direction="memory"):
        self.base, self.layout_bonus, self.wrong, self.direction = (
            base, layout_bonus, wrong, direction)

    def evaluate(self, s_path, with_counters=False):
        name = os.path.basename(s_path)
        tflops = self.base + (self.layout_bonus if "agent_layout" in name else 0.0)
        correct = not self.wrong
        d = {"bottleneck": self.direction} if with_counters else None
        return type("R", (), {"compiled": True, "correct": correct, "tflops": tflops,
                              "direction": d})()


def _loads(src):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    reg = regions.analyze(prog, t).regions[0]
    ed = RegionEditor(prog, t, reg, treat_waitcnt_as_fence=False)
    return ed, [i for i in ed.order if ed.kind_of(i) is Kind.VMEM_LOAD]


class TestObserve(unittest.TestCase):
    def setUp(self):
        self.sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False)

    def test_facts_map_shape(self):
        obs = self.sess.observe(with_direction=False)
        self.assertEqual(len(obs.anchors), 5)            # 5 MFMA
        self.assertEqual(len(obs.slots), 4)              # 4 gaps between them
        kinds = {f.kind for f in obs.fillers}
        self.assertIn("vmem_load", kinds)
        self.assertTrue(all(len(f.legal_window) == 2 for f in obs.fillers))

    def test_serialisable(self):
        obs = self.sess.observe(with_direction=False)
        d = obs.to_dict()
        import json
        json.loads(json.dumps(d))                        # must be JSON-able for an LLM

    def test_direction_included(self):
        obs = self.sess.observe(with_direction=True)
        self.assertIsNotNone(obs.direction)
        self.assertEqual(obs.direction.get("bottleneck"), "memory")


class TestPropose(unittest.TestCase):
    def test_legal_layout_all_placed(self):
        ed, loads = _loads(_SYNTH)
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False)
        cand = {0: [loads[0], loads[1]], 1: [loads[2]], 2: [loads[3]]}
        out = sess.propose([cand])[0]
        self.assertTrue(out.legal)
        self.assertEqual(len(out.placed), 4)
        self.assertFalse(out.skipped)

    def test_out_of_range_slot_reported(self):
        ed, loads = _loads(_SYNTH)
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False)
        out = sess.propose([{99: [loads[0]]}])[0]        # no such slot
        reasons = [s["reason"] for s in out.skipped]
        self.assertIn(SkipReason.SLOT_OOR.value, reasons)

    def test_non_committing(self):
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False)
        before = sess.observe(with_direction=False).to_dict()
        _, loads = _loads(_SYNTH)
        sess.propose([{0: [loads[0]]}])
        after = sess.observe(with_direction=False).to_dict()
        self.assertEqual(before["slots"], after["slots"])   # seed untouched


class TestCommitEval(unittest.TestCase):
    def setUp(self):
        self.store = tempfile.mkdtemp(prefix="testft_sess_store_")

    def test_accepts_faster_layout(self):
        _, loads = _loads(_SYNTH)
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            store=self.store)
        res = sess.commit_and_eval({0: [loads[0]], 1: [loads[1]],
                                    2: [loads[2]], 3: [loads[3]]})
        self.assertTrue(res.correct)
        self.assertTrue(res.accepted)                    # layout > baseline
        self.assertGreater(res.tflops, res.baseline_tflops)

    def test_rejects_incorrect_layout(self):
        _, loads = _loads(_SYNTH)
        sess = AgentSession(_SYNTH, _FakeEval(wrong=True), protect_prefetch=False,
                            store=self.store)
        res = sess.commit_and_eval({0: [loads[0]]})
        self.assertFalse(res.accepted)                   # correctness gate

    def test_logs_decision(self):
        _, loads = _loads(_SYNTH)
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            store=self.store, context={"kernel": "synth"})
        sess.commit_and_eval({0: [loads[0]]})
        log = os.path.join(self.store, "experiments.log")
        self.assertTrue(os.path.exists(log))
        with open(log) as f:
            self.assertIn("llm_agent", f.read())


# a tiny loop kernel: prologue (setup) + a back-edge loop + epilogue (store).
_LOOP_KERNEL = """.text
k:
  s_mov_b32 s0, 0
  s_mov_b32 s1, 16
  v_mov_b32 v0, 0
label_top:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  buffer_load_dwordx4 v[4:7], v64, s[0:3], 0 offen
  s_add_u32 s0, s0, 1
  s_cmp_lt_u32 s0, s1
  s_cbranch_scc1 label_top
  v_mov_b32 v10, v36
  v_mov_b32 v11, v40
  s_endpgm
""".format(m=MFMA)


class TestRegionSelection(unittest.TestCase):
    """The agent can target prologue / loop / epilogue independently."""

    def test_observe_lists_all_regions(self):
        sess = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False)
        obs = sess.observe(with_direction=False)
        kinds = [r["kind"] for r in obs.regions]
        self.assertIn("loop", kinds)
        self.assertIn("prologue", kinds)
        self.assertIn("epilogue", kinds)
        self.assertEqual(obs.region, "loop")             # default selection
        # every region reports a positive instruction count + a stable index
        self.assertTrue(all(r["instrs"] > 0 for r in obs.regions))
        self.assertEqual([r["index"] for r in obs.regions],
                         list(range(len(obs.regions))))

    def test_selected_region_changes_view(self):
        loop_obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                                region="loop").observe(with_direction=False)
        epi_obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                               region="epilogue").observe(with_direction=False)
        self.assertEqual(loop_obs.region, "loop")
        self.assertEqual(epi_obs.region, "epilogue")
        # the loop has MFMA anchors; the epilogue (no MFMA) does not
        self.assertGreater(len(loop_obs.anchors), 0)
        self.assertEqual(len(epi_obs.anchors), 0)

    def test_build_candidate_per_region_legal(self):
        from search import driver
        for region in ("prologue", "loop", "epilogue"):
            text, ok = driver.build_candidate(
                _LOOP_KERNEL, {"kind": "ladder", "level": 1, "region": region})
            self.assertTrue(ok, "ladder recompute must verify for %s" % region)
            self.assertIn("s_endpgm", text)

    def test_missing_region_raises(self):
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            region="epilogue")
        # _SYNTH has no loop -> a single region; asking for epilogue is an error
        with self.assertRaises(ValueError):
            sess.observe(with_direction=False)


class TestDagObserve(unittest.TestCase):
    """Anchor-less regions (no MFMA) expose a dependency-DAG view instead of the
    MFMA slot/filler model (proj/anchorless_region_scheduling.md, Phase 1)."""

    def test_epilogue_exposes_dag(self):
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                           region="epilogue").observe(with_direction=False)
        self.assertEqual(obs.region, "epilogue")
        self.assertEqual(len(obs.anchors), 0)            # no MFMA in epilogue
        self.assertFalse(obs.slots)                      # slot model degenerate
        self.assertIsNotNone(obs.dag)
        self.assertGreater(len(obs.dag), 0)
        for n in obs.dag:
            self.assertEqual(len(n["legal_window"]), 2)
            self.assertIn("kind", n)
            self.assertIn("preds", n)
            self.assertIn("succs", n)

    def test_loop_region_has_no_dag(self):
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                           region="loop").observe(with_direction=False)
        self.assertGreater(len(obs.anchors), 0)          # loop has MFMA anchors
        self.assertIsNone(obs.dag)                       # slot model used, no DAG

    def test_dag_serialisable(self):
        import json
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                           region="prologue").observe(with_direction=False)
        json.loads(json.dumps(obs.to_dict()))            # must be JSON-able for an LLM

    def test_listsched_builds_legal_on_anchorless_region(self):
        from search import driver
        from search.list_scheduler import Weights
        for region in ("prologue", "epilogue"):
            text, ok = driver.build_candidate(
                _LOOP_KERNEL, {"kind": "listsched", "weights": Weights(),
                               "region": region})
            self.assertTrue(ok, "listsched must verify for %s" % region)
            self.assertIn("s_endpgm", text)


# anchor-less kernel with async scalar loads + an explicit wait (no MFMA): used
# to check the DAG view's counter semantics + waitcnt preview (M9 Phase 2b).
_ASYNC_KERNEL = """.text
k:
  s_load_dwordx2 s[0:1], s[8:9], 0
  s_load_dwordx2 s[2:3], s[8:9], 8
  s_waitcnt lgkmcnt(0)
  v_add_f32 v0, v0, v1
  s_endpgm
"""


class TestWaitcntPreview(unittest.TestCase):
    """DAG nodes carry counter semantics + observe reports a waitcnt preview with
    the cost-model scalar (M9 Phase 2b)."""

    def test_counter_semantics_in_dag(self):
        obs = AgentSession(_ASYNC_KERNEL, _FakeEval(),
                           protect_prefetch=False).observe(with_direction=False)
        self.assertIsNotNone(obs.dag)
        by_kind = {}
        for n in obs.dag:
            by_kind.setdefault(n["kind"], []).append(n)
        # s_load bumps the lgkm counter
        self.assertTrue(any(n["bumps_counter"] == "lgkm"
                            for n in by_kind.get("smem", [])))
        # the wait node reports what it waits on
        waits = [n for n in obs.dag if n["waits_on"]]
        self.assertTrue(waits)
        self.assertIn("lgkm", waits[0]["waits_on"])

    def _loop_share_fraction(self, loop_trips):
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                           loop_trips=loop_trips).observe(with_direction=False)
        by = {r["kind"]: r for r in obs.regions}
        total = sum(r["est_share"] for r in obs.regions)
        return by["loop"]["est_share"] / total

    def test_est_share_shape_aware(self):
        # the SHARE of total time attributed to the loop falls as the loop runs
        # fewer times -> the tails' relative weight rises (shape-adaptive).
        big = self._loop_share_fraction(1000)
        small = self._loop_share_fraction(1)
        self.assertGreater(big, 0.99)                    # large K: loop dominates
        self.assertLess(small, big)                      # tiny K: tails matter more

    def test_est_share_none_when_trips_unknown(self):
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False
                           ).observe(with_direction=False)
        loop = next(r for r in obs.regions if r["kind"] == "loop")
        self.assertIsNone(loop["est_share"])             # unknown -> honest None
        self.assertIn("est_cycles", loop)                # still reported

    def test_waitcnt_preview_present(self):
        obs = AgentSession(_ASYNC_KERNEL, _FakeEval(),
                           protect_prefetch=False).observe(with_direction=False)
        wp = obs.waitcnt_preview
        self.assertIsNotNone(wp)
        self.assertIn("cost", wp)
        self.assertIn("est_cycles", wp["cost"])
        self.assertTrue(wp["waits"])                     # the lgkmcnt(0) wait
        import json
        json.loads(json.dumps(obs.to_dict()))


# anchor-less kernel with a long TIGHT RAW chain (address-calc-like: each op
# consumes the previous one's result, so interior nodes are pinned) plus two
# independent async scalar loads: used to check the tunable subset shrinks the
# DAG to the few worth-moving nodes (proj/brainstorm/large_dag_finetune.md).
_BIGDAG_KERNEL = """.text
k:
  s_load_dwordx2 s[0:1], s[8:9], 0
  s_load_dwordx2 s[2:3], s[8:9], 8
  v_add_u32 v2, v2, v3
  v_add_u32 v4, v2, v5
  v_add_u32 v6, v4, v7
  v_add_u32 v8, v6, v9
  v_add_u32 v10, v8, v11
  s_waitcnt lgkmcnt(0)
  v_add_f32 v0, v0, v1
  s_endpgm
"""


class TestTunableSubset(unittest.TestCase):
    """M-large-dag Phase 1a: observe exposes a small "worth-moving" subset of an
    anchor-less region's DAG (proj/brainstorm/large_dag_finetune.md direction 1)."""

    def _obs(self, **kw):
        return AgentSession(_BIGDAG_KERNEL, _FakeEval(), protect_prefetch=False,
                            **kw).observe(with_direction=False)

    def test_tunable_is_subset_of_dag(self):
        obs = self._obs()
        self.assertIsNotNone(obs.tunable)
        dag_iids = {n["iid"] for n in obs.dag}
        self.assertTrue(set(obs.tunable) <= dag_iids)
        # no fence is ever tunable
        fences = {n["iid"] for n in obs.dag if n["is_fence"]}
        self.assertFalse(set(obs.tunable) & fences)

    def test_tunable_smaller_than_full_dag(self):
        obs = self._obs()
        self.assertLess(len(obs.tunable), len(obs.dag))   # pruned
        # the two async scalar loads (bump lgkm, movable) are worth moving
        load_iids = [n["iid"] for n in obs.dag if n["kind"] == "smem"]
        for li in load_iids:
            self.assertIn(li, obs.tunable)

    def test_tunable_none_for_anchored_region(self):
        # anchored region (has MFMA): dag is None, so tunable is None too
        anchored = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                                region="loop").observe(with_direction=False)
        self.assertGreater(len(anchored.anchors), 0)
        self.assertIsNone(anchored.tunable)

    def test_serializable(self):
        import json
        json.loads(json.dumps(self._obs().to_dict()))


class TestFenceSegmentsAndCritical(unittest.TestCase):
    """M-large-dag Phase 2: fence-segmentation + critical-path focus for an
    anchor-less region (large_dag_finetune.md directions 2/3)."""

    def _obs(self):
        return AgentSession(_BIGDAG_KERNEL, _FakeEval(), protect_prefetch=False
                            ).observe(with_direction=False)

    def test_segments_present_and_costed(self):
        obs = self._obs()
        self.assertIsNotNone(obs.segments)
        self.assertTrue(obs.segments)
        for s in obs.segments:
            self.assertIn("seg_id", s)
            self.assertIn("iids", s)
            self.assertIn("est_cycles", s)
            self.assertTrue(s["iids"])
        # segments partition non-fence work: their union has no fence
        fences = {n["iid"] for n in obs.dag if n["is_fence"]}
        seg_iids = {i for s in obs.segments for i in s["iids"]}
        self.assertFalse(seg_iids & fences)

    def test_critical_focus(self):
        obs = self._obs()
        self.assertIsNotNone(obs.critical)
        self.assertIn("top_k", obs.critical)
        # the lgkmcnt(0) wait drains the two async scalar loads -> feeders name them
        dw = obs.critical["dominant_wait"]
        self.assertIsNotNone(dw)
        self.assertEqual(dw["counter"], "lgkm")
        load_iids = {n["iid"] for n in obs.dag if n["kind"] == "smem"}
        self.assertTrue(set(dw["feeders"]) & load_iids)

    def test_anchored_region_has_no_segments(self):
        obs = AgentSession(_LOOP_KERNEL, _FakeEval(), protect_prefetch=False,
                           region="loop").observe(with_direction=False)
        self.assertIsNone(obs.segments)
        self.assertIsNone(obs.critical)


class TestSuggestOrders(unittest.TestCase):
    """M-large-dag Phase 3: engine-generated seed reorders for an anchor-less
    region (large_dag_finetune.md direction 4)."""

    def test_suggest_returns_legal_costed_orders(self):
        sess = AgentSession(_BIGDAG_KERNEL, _FakeEval(), protect_prefetch=False)
        res = sess.suggest_orders(n=3)
        self.assertIn("baseline_est_cycles", res)
        self.assertTrue(res["candidates"])
        seen_iids = None
        for c in res["candidates"]:
            self.assertIn("weights", c)
            self.assertIsNotNone(c["est_cycles"])
            # every suggested order is a legal permutation validated by propose
            rep = sess.propose_orders([c["order"]])[0]
            self.assertTrue(rep["legal"])
            iids = set(c["order"])
            if seen_iids is None:
                seen_iids = iids
            self.assertEqual(iids, seen_iids)             # same node set each time

    def test_suggest_sorted_by_est_cycles(self):
        sess = AgentSession(_BIGDAG_KERNEL, _FakeEval(), protect_prefetch=False)
        cands = sess.suggest_orders(n=3)["candidates"]
        costs = [c["est_cycles"] for c in cands]
        self.assertEqual(costs, sorted(costs))            # ascending est_cycles


class TestCompactObservation(unittest.TestCase):
    """M-large-dag Phase 1b: --compact trims the anchor-less dag to a per-node
    summary and spills the full dag to a sidecar .jsonl."""

    def test_compact_trims_and_spills(self):
        import json as _json
        import tools.agent_session as ags
        out = tempfile.mkdtemp(prefix="testft_compact_")
        obs = AgentSession(_BIGDAG_KERNEL, _FakeEval(), protect_prefetch=False
                           ).observe(with_direction=False).to_dict()
        d = ags._compact_observation(obs, "body", "bigdag.s", out)
        for n in d["dag"]:
            self.assertNotIn("preds", n)              # heavy fields dropped
            self.assertNotIn("succs", n)
            self.assertIn("bumps_counter", n)         # summary kept
        self.assertEqual(os.path.dirname(d["dag_full_path"]), out)
        with open(d["dag_full_path"]) as f:
            first = _json.loads(f.readline())
        self.assertIn("preds", first)                 # full node in sidecar

    def test_compact_noop_without_dag(self):
        import tools.agent_session as ags
        d = ags._compact_observation({"dag": None}, "loop", "k.s", tempfile.gettempdir())
        self.assertIsNone(d["dag"])
        self.assertNotIn("dag_full_path", d)


class TestProposeOrders(unittest.TestCase):
    """M9 Phase 3a: anchor-less linear-order intents (propose_orders +
    commit_and_eval_order)."""

    def _iids(self):
        obs = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False
                           ).observe(with_direction=False)
        return [n["iid"] for n in obs.dag]

    def test_legal_order_intent_all_placed(self):
        iids = self._iids()
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False)
        rep = sess.propose_orders([iids])[0]              # the identity order
        self.assertTrue(rep["legal"])
        self.assertEqual(len(rep["placed"]), len(iids))
        self.assertFalse(rep["skipped"])
        self.assertIn("est_cycles", rep["cost"])

    def test_unknown_iid_skipped(self):
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False)
        rep = sess.propose_orders([[999999]])[0]          # not in region
        self.assertTrue(rep["skipped"])
        self.assertEqual(rep["skipped"][0]["reason"], SkipReason.SLOT_OOR.value)

    def test_non_committing(self):
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False)
        before = sess.observe(with_direction=False).to_dict()["dag"]
        sess.propose_orders([list(reversed(self._iids()))])
        after = sess.observe(with_direction=False).to_dict()["dag"]
        self.assertEqual(before, after)                   # seed untouched

    def test_commit_order_runs_gate(self):
        iids = self._iids()
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False,
                            store=tempfile.mkdtemp(prefix="testft_order_"))
        res = sess.commit_and_eval_order(iids)
        self.assertTrue(res.correct)
        self.assertIsNotNone(res.est_cycles)

    def test_overlong_intent_rejected_without_eval(self):
        """Phase 0 guardrail: an order longer than max_order_intent is rejected
        in O(1) with an error + hint, never evaluated, and the seed is untouched
        (proj/brainstorm/anchorless_fullorder_propose_perf.md)."""
        iids = self._iids()
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False,
                            max_order_intent=len(iids) - 1)
        before = sess.observe(with_direction=False).to_dict()["dag"]
        rep = sess.propose_orders([iids])[0]              # too long by one
        self.assertFalse(rep["legal"])
        self.assertIn("error", rep)
        self.assertIn("partial order", rep["error"])
        self.assertFalse(rep["placed"])                   # not evaluated
        after = sess.observe(with_direction=False).to_dict()["dag"]
        self.assertEqual(before, after)                   # seed untouched

    def test_at_limit_intent_accepted(self):
        """A boundary intent (exactly max_order_intent) is still evaluated."""
        iids = self._iids()
        sess = AgentSession(_ASYNC_KERNEL, _FakeEval(), protect_prefetch=False,
                            max_order_intent=len(iids))
        rep = sess.propose_orders([iids])[0]
        self.assertNotIn("error", rep)
        self.assertTrue(rep["legal"])


class TestAdaptiveVerdict(unittest.TestCase):
    """M9 Phase 2d: real-HW TFLOPS decides; the cost model only breaks ties
    inside the noise band and never overturns a measured regression."""

    def _sess(self, margin=0.1):
        return AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            noise_margin=margin)

    def test_incorrect_rejected(self):
        ok, note = self._sess()._verdict(False, 200.0, 100.0, 5, 10)
        self.assertFalse(ok)
        self.assertIn("incorrect", note)

    def test_faster_beyond_noise_accepted(self):
        ok, _ = self._sess()._verdict(True, 130.0, 100.0, 99, 1)  # cost worse...
        self.assertTrue(ok)                                       # ...but TFLOPS wins

    def test_slower_beyond_noise_rejected(self):
        ok, _ = self._sess()._verdict(True, 80.0, 100.0, 1, 99)   # cost better...
        self.assertFalse(ok)                                      # ...real HW still rejects

    def test_within_noise_uses_cost_tiebreak(self):
        s = self._sess(margin=0.1)
        # tflops within +-10% of baseline -> cost model decides
        ok_better, _ = s._verdict(True, 101.0, 100.0, 5, 10)
        ok_worse, _ = s._verdict(True, 101.0, 100.0, 10, 5)
        self.assertTrue(ok_better)                                # lower est_cycles -> accept
        self.assertFalse(ok_worse)                                # no gain -> keep baseline


@unittest.skipUnless(os.path.exists(SHADER), "real gemm seed not present")
class TestRealSeed(unittest.TestCase):
    def test_observe_real_gemm(self):
        with open(SHADER) as fh:
            src = fh.read()
        sess = AgentSession(src, _FakeEval(), protect_prefetch=True)
        obs = sess.observe(with_direction=False)
        self.assertGreater(len(obs.anchors), 0)
        self.assertGreater(len(obs.prefetch_loads), 0)   # prefetch recognised
        # prefetch loads must be flagged in the filler views too
        flagged = {f.iid for f in obs.fillers if f.is_prefetch}
        self.assertTrue(flagged & set(obs.prefetch_loads))


class TestPlanLayouts(unittest.TestCase):
    """Layer 3: AgentSession.plan_layouts consumes gold-mined QUANT constraints
    from the knowledge store and emits ranked, propose-validated candidate gap
    layouts for THIS kernel's fillers -- no GPU needed (propose is CPU-only)."""

    def setUp(self):
        from agent import knowledge as kn
        from agent.knowledge import Skill
        self.store = tempfile.mkdtemp(prefix="testft_plan_store_")
        kn.save_skill(Skill(
            id="gold-mfma_dense-loop-quant", statement="",
            when={"arch": "gfx942", "loop_kind": "mfma_dense", "region": "loop"},
            action={"constraints": [
                {"metric": "mfma_gap_size", "stat": {"median": 1, "max": 3},
                 "weight": 0.9},
                {"metric": "per_slot_capacity", "kind": "vmem_load",
                 "stat": {"median": 1, "max": 1}, "weight": 0.9},
                {"metric": "adjacent_cooccur", "kind": "vmem_load",
                 "value": 0.9, "polarity": "ok", "weight": 0.87}]},
            confidence=0.85, status="candidate"), self.store)
        self.ctx = {"arch": "gfx942", "loop_kind": "mfma_dense"}

    def _sess(self):
        return AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            store=self.store, context=self.ctx, region="loop")

    def test_plan_emits_validated_candidates(self):
        plans = self._sess().plan_layouts(max_candidates=3)
        self.assertTrue(plans, "constraints in store must yield candidate layouts")
        for p in plans:
            for key in ("layout", "score", "legal", "n_placed"):
                self.assertIn(key, p)
        # the measured "1 vmem per slot, neighbours ok" prior spreads the 4 loads
        # across the 4 MFMA gaps; that intent must be engine-legal on CPU.
        self.assertTrue(any(p["legal"] and p["n_placed"] > 0 for p in plans))

    def test_plan_empty_without_constraints_in_store(self):
        empty_store = tempfile.mkdtemp(prefix="testft_plan_empty_")
        sess = AgentSession(_SYNTH, _FakeEval(), protect_prefetch=False,
                            store=empty_store, context=self.ctx, region="loop")
        self.assertEqual(sess.plan_layouts(), [])

    def test_plan_skipped_validation_has_no_legal_key(self):
        plans = self._sess().plan_layouts(max_candidates=2, validate=False)
        self.assertTrue(plans)
        self.assertNotIn("legal", plans[0])

    # --- the real-HW validation SWITCH (learn_layouts) --------------------
    def test_learn_offline_never_touches_evaluator(self):
        # validate=False must derive + propose-validate candidates on CPU and
        # NEVER call the evaluator -- so skills can be summarised for any arch
        # on a GPU-less box. We prove it with an evaluator that explodes if used.
        class _Boom:
            def evaluate(self, *a, **k):
                raise AssertionError("evaluator must NOT be called when validate=False")
        sess = AgentSession(_SYNTH, _Boom(), protect_prefetch=False,
                            store=self.store, context=self.ctx, region="loop")
        out = sess.learn_layouts(validate=False, max_candidates=3)
        self.assertFalse(out["validated"])
        self.assertGreater(out["n_candidates"], 0)
        self.assertNotIn("results", out)

    def test_learn_online_commits_and_can_promote(self):
        sess = self._sess()
        out = sess.learn_layouts(validate=True, max_candidates=3, promote=True)
        self.assertTrue(out["validated"])
        self.assertGreater(out["n_legal"], 0)
        self.assertTrue(out["results"])
        # _FakeEval scores 'agent_layout' candidates above baseline -> accepted
        self.assertIsNotNone(out["best"])
        self.assertIn("promoted", out)
        # the commit was logged to the experiments log under the store
        self.assertTrue(os.path.exists(os.path.join(self.store, "experiments.log")))

    def test_validate_skills_tool_dry_and_injected(self):
        from tools import validate_skills as vs
        # dry (validate=False) -> CPU plan, evaluator never used
        class _Boom:
            def evaluate(self, *a, **k):
                raise AssertionError("dry validate must not call evaluator")
        dry = vs.validate_skill_layouts(_SYNTH, _Boom(), store=self.store,
                                        context=self.ctx, region="loop",
                                        validate=False)
        self.assertFalse(dry["validated"])
        # injected fake evaluator -> HW path commits
        wet = vs.validate_skill_layouts(_SYNTH, _FakeEval(), store=self.store,
                                        out_store=self.store, context=self.ctx,
                                        region="loop", validate=True)
        self.assertTrue(wet["validated"])
        self.assertTrue(wet["results"])


if __name__ == "__main__":
    unittest.main()
