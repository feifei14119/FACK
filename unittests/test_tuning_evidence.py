"""CPU regressions for screening provenance; no GPU or compiler is needed."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from agent import knowledge
from agent.artifacts import save_assembly
from agent.session import AgentSession
from harness.evaluator import EvalResult
from harness.measurement import file_sha256, measure_screen
from search import driver
from tools import agent_session, tune_summarize
from unittests.test_session import _SYNTH, _loads


class SequenceEvaluator:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def evaluate(self, path, with_counters=False):
        self.calls.append(path)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


def good(score=100.0, **kwargs):
    return EvalResult(compiled=True, correct=True, tflops=score, **kwargs)


class TestMeasurements(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "candidate.s")
        Path(self.path).write_text(".text\n", encoding="utf-8")

    def test_raw_samples_and_median_survive_serialization(self):
        batch = measure_screen(SequenceEvaluator([
            good(100, detail={"build": "a.co"}), good(300), good(110)]), self.path, 3)
        self.assertEqual((batch.status, batch.correct, batch.tflops), ("measured", True, 110))
        rows = json.loads(json.dumps(batch.to_dict(), allow_nan=False))["samples"]
        self.assertEqual([r["result"]["tflops"] for r in rows], [100, 300, 110])
        self.assertEqual(rows[0]["result"]["detail"], {"build": "a.co"})
        self.assertEqual(rows[0]["source_sha256"], file_sha256(self.path))

    def test_unknown_correctness_cannot_borrow_another_samples_pass(self):
        ev = SequenceEvaluator([good(), EvalResult(True, None, tflops=900), good(900)])
        batch = measure_screen(ev, self.path, 3)
        self.assertEqual(batch.status, "measurement_invalid")
        self.assertIsNone(batch.correct)
        self.assertIsNone(batch.tflops)
        self.assertEqual(len(ev.calls), 2)
        # The compatibility search helper must enforce the same gate.
        self.assertEqual(driver._median_tflops(SequenceEvaluator([
            good(), EvalResult(True, None, tflops=900)]), self.path, 2), (None, None))

    def test_failures_are_distinct_and_stop_repetitions(self):
        cases = [(EvalResult(False, True, tflops=900), "compile_failed", None),
                 (EvalResult(True, False, tflops=900), "incorrect", False),
                 (RuntimeError("client failed"), "measurement_invalid", None)]
        for result, status, correct in cases:
            with self.subTest(status=status):
                ev = SequenceEvaluator([good(), result, good(900)])
                batch = measure_screen(ev, self.path, 3)
                self.assertEqual(batch.status, status)
                self.assertIs(batch.correct, correct)
                self.assertIsNone(batch.tflops)
                self.assertEqual(len(ev.calls), 2)

    def test_invalid_scores_never_enter_ranking(self):
        for score in (float("nan"), float("inf"), -1.0, 0.0, True, "100", None):
            with self.subTest(score=score):
                batch = measure_screen(SequenceEvaluator([good(score)]), self.path, 1)
                self.assertEqual(batch.status, "measurement_invalid")
                self.assertIsNone(batch.tflops)
                json.dumps(batch.to_dict(), allow_nan=False)

    def test_missing_compilation_verdict_is_not_pass(self):
        batch = measure_screen(SequenceEvaluator([type("R", (), {
            "correct": True, "tflops": 100.0})()]), self.path, 1)
        self.assertEqual(batch.status, "measurement_invalid")

    def test_source_mutation_discards_even_a_pass(self):
        path = self.path

        class MutatingEvaluator:
            def evaluate(self, path, with_counters=False):
                Path(path).write_text("changed\n", encoding="utf-8")
                return good(999)

        batch = measure_screen(MutatingEvaluator(), path, 1)
        self.assertEqual(batch.status, "measurement_invalid")
        self.assertIsNone(batch.tflops)
        self.assertEqual(batch.samples[0]["result"]["tflops"], 999)
        self.assertIn("changed during", batch.error)

    def test_digest_mismatch_never_calls_client(self):
        ev = SequenceEvaluator([good()])
        batch = measure_screen(ev, self.path, 1, expected_sha256="wrong")
        self.assertEqual(batch.status, "measurement_invalid")
        self.assertFalse(ev.calls)


class TestAssemblyEvidence(unittest.TestCase):
    def test_preserves_exact_bytes_and_refuses_corrupted_archive(self):
        with tempfile.TemporaryDirectory() as out:
            text = "; 原始\r\n.text\r\n"
            artifact = save_assembly(text, out)
            self.assertEqual(Path(artifact["path"]).read_bytes(), text.encode("utf-8"))
            self.assertEqual(save_assembly(text, out), artifact)
            Path(artifact["path"]).write_text("bad", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                save_assembly(text, out)

    def test_default_output_is_not_curated_knowledge(self):
        sess = AgentSession(_SYNTH, SequenceEvaluator([]))
        self.assertEqual(sess.out_store, knowledge.DEFAULT_OUT_STORE)

    def test_commit_preserves_three_identities_and_raw_measurements(self):
        _, loads = _loads(_SYNTH)
        with tempfile.TemporaryDirectory() as out:
            ev = SequenceEvaluator([good(100), good(110)])
            sess = AgentSession(_SYNTH, ev, out_store=out, perf_repeats=1,
                                protect_prefetch=False)
            res = sess.commit_and_eval({0: [loads[0]]})
            self.assertTrue(res.accepted)
            self.assertEqual((res.stage, res.verdict), ("screen", "screening_gain"))
            self.assertEqual(len(ev.calls), 2)  # no new original/confirmation HW calls
            evidence = res.evidence
            self.assertEqual(evidence["original"]["measurement_status"], "not_measured")
            self.assertIsNone(evidence["original"]["measurement"])
            self.assertEqual(evidence["original"]["artifact"]["sha256"],
                             hashlib.sha256(_SYNTH.encode("utf-8")).hexdigest())
            for role in ("original", "normalized", "candidate"):
                artifact = evidence[role]["artifact"]
                self.assertEqual(file_sha256(artifact["path"]), artifact["sha256"])
            self.assertEqual(evidence["normalized"]["measurement"]["tflops"], 100)
            self.assertEqual(evidence["candidate"]["measurement"]["tflops"], 110)
            rows_path = os.path.join(out, "run.results.jsonl")
            agent_session._append_result(rows_path, "loop", {0: [loads[0]]}, res,
                                          shader=sess.last_archive)
            row = json.loads(Path(rows_path).read_text())
            self.assertEqual(row["baseline_kind"], "normalized")
            self.assertEqual(row["artifact_sha256"], file_sha256(row["shader"]))
            self.assertEqual(row["evidence"], json.loads(json.dumps(evidence)))

    def test_bad_baseline_prevents_candidate_and_cached_fail_is_not_retried(self):
        for first in (EvalResult(True, False, tflops=100),
                      EvalResult(True, None, tflops=100), EvalResult(False)):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as out:
                ev = SequenceEvaluator([first])
                sess = AgentSession(_SYNTH, ev, out_store=out, perf_repeats=1)
                for _ in range(2):
                    res = sess.commit_and_eval({})
                    self.assertEqual(res.verdict, "baseline_failed")
                    self.assertFalse(res.accepted)
                    self.assertIsNone(res.correct)  # candidate was not measured
                    self.assertIsNone(sess.last_archive)
                self.assertEqual(len(ev.calls), 1)
                self.assertEqual(knowledge.induce_skills(out), [])

    def test_invalid_candidate_does_not_teach_performance_avoid(self):
        with tempfile.TemporaryDirectory() as out:
            sess = AgentSession(_SYNTH, SequenceEvaluator([
                good(), EvalResult(True, None, tflops=999)]), out_store=out, perf_repeats=1)
            res = sess.commit_and_eval({})
            self.assertEqual(res.verdict, "measurement_invalid")
            self.assertFalse(res.accepted)
            self.assertEqual(knowledge.induce_skills(out), [])
            self.assertEqual(knowledge.read_experiments(out)[0]["verdict"], res.verdict)

    def test_cost_tie_is_exploration_only(self):
        with tempfile.TemporaryDirectory() as out:
            sess = AgentSession(_SYNTH, SequenceEvaluator([good(), good(101)]),
                                out_store=out, perf_repeats=1, noise_margin=0.1)
            with mock.patch.object(sess, "_region_cost", return_value=5), \
                    mock.patch.object(sess, "_baseline_region_cost", return_value=10):
                res = sess.commit_and_eval({})
            self.assertTrue(res.accepted)  # existing search policy retained
            self.assertEqual(res.verdict, "exploration_only")
            self.assertEqual(res.stage, "screen")

    def test_failed_commit_never_reuses_previous_shader_path(self):
        with tempfile.TemporaryDirectory() as out:
            sess = AgentSession(_SYNTH, SequenceEvaluator([good(), good(110)]),
                                out_store=out, perf_repeats=1)
            sess.commit_and_eval({})
            self.assertIsNotNone(sess.last_archive)
            with mock.patch.object(driver, "build_candidate", return_value=("", False)):
                res = sess.commit_and_eval({})
            self.assertEqual(res.verdict, "illegal")
            self.assertIsNone(sess.last_archive)

    def test_cli_records_verbatim_params_and_original_line_endings(self):
        with tempfile.TemporaryDirectory() as out:
            text = _SYNTH.replace("\n", "\r\n")
            seed = Path(out, "seed.s")
            seed.write_bytes(text.encode("utf-8"))
            results = Path(out, "run.results.jsonl")
            cl = SimpleNamespace(spec="example/case", out_dir=out)
            ev = SequenceEvaluator([good()] * 3 + [good(110)] * 3)
            params = ["--x", "2", "--x", "1"]
            with mock.patch.object(agent_session, "_client", return_value=cl), \
                    mock.patch.object(agent_session, "_make_evaluator", return_value=ev), \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = agent_session.main(["eval", str(seed), "--client", cl.spec,
                                         "--results-path", str(results), "--"] + params)
            self.assertEqual(rc, 0)
            row = json.loads(results.read_text())
            self.assertEqual(row["evidence"]["evaluation_contract"]["params"], params)
            original = row["evidence"]["original"]["artifact"]
            self.assertEqual(Path(original["path"]).read_bytes(), seed.read_bytes())
            self.assertEqual(len(ev.calls), 6)


class TestScreeningSummary(unittest.TestCase):
    def _summarize(self, directory, rows):
        path = os.path.join(directory, "run.results.jsonl")
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tune_summarize.main(["--results", path, "--out", directory]), 0)
        return json.loads(Path(directory, "run.summary.json").read_text())

    def test_legacy_high_score_is_not_confirmation(self):
        with tempfile.TemporaryDirectory() as out:
            summary = self._summarize(out, [
                {"correct": True, "tflops": 100, "accepted": True},
                {"correct": True, "tflops": 1000, "accepted": True},
                {"correct": False, "tflops": 9000},
                {"correct": True, "tflops": float("inf")},
                {"correct": True, "tflops": 2000, "compiled": False},
                {"correct": "True", "tflops": 3000},
                ["not a row"]])
            self.assertEqual(summary["screening_best"]["tflops"], 1000)
            self.assertEqual(summary["best"], summary["screening_best"])
            self.assertEqual(summary["confirmation_status"], "not_performed")
            self.assertIsNone(summary["recommendation"])
            self.assertIsNone(summary["confirmed_best"])

    def test_copy_checks_evidence_digest(self):
        with tempfile.TemporaryDirectory() as out:
            artifact = save_assembly(".text\n", out)
            row = {"correct": True, "tflops": 100, "shader": artifact["path"],
                   "artifact_sha256": artifact["sha256"], "stage": "screen"}
            summary = self._summarize(out, [row])
            self.assertEqual(summary["archive_status"], "digest_verified")
            self.assertIn("screening_best_tf", summary["best_shader"])
            copied = os.path.join(tune_summarize._REPO, summary["best_shader"])
            self.assertEqual(file_sha256(copied), artifact["sha256"])
            Path(artifact["path"]).write_text("changed", encoding="utf-8")
            summary = self._summarize(out, [row])
            self.assertEqual(summary["archive_status"], "digest_mismatch")
            self.assertIsNone(summary["best_shader"])

    def test_invalid_measurement_with_score_is_excluded(self):
        with tempfile.TemporaryDirectory() as out:
            summary = self._summarize(out, [
                {"correct": True, "tflops": 900, "verdict": "measurement_invalid"}])
            self.assertIsNone(summary["best"])
            self.assertIsNone(summary["recommendation"])


if __name__ == "__main__":
    unittest.main()
