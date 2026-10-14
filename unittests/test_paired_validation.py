"""Fixed paired inference and durable promotion/finalization, entirely on CPU."""
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from agent import run as run_module
from agent.run import RunController
from harness.comparison import assess_pairs, lower_rank, pair_order, validate_policy
from harness.evaluator import EvalResult
from unittests.test_session import _SYNTH
from unittests.test_tuning_run import (CONTRACT, FakeEvaluator, assert_error, cli,
                                      passed, prepare)


POLICY = {"method": "paired_sign_v1", "confirm_pairs": 8, "final_pairs": 8,
          "min_gain": 0.01, "alpha": 0.05, "max_confirmations": 3}


def pairs(ratios):
    return [{"reference": 100, "candidate": 100 * r} for r in ratios]


def evaluator(stage="confirm", reference=100, candidate=110):
    scores = {"reference": reference, "candidate": candidate}
    return FakeEvaluator(*(passed(scores[role]) for i in range(POLICY[stage + "_pairs"])
                           for role in pair_order(i)))


def test_sign_bounds_match_exact_small_binomial_examples():
    assert lower_rank(8, 0.05) == 2  # P(Bin(8,.5) <= 1) = 9/256
    assert lower_rank(8, 0.05 / 3) == 1
    assert lower_rank(4, 0.05) == 0
    result = assess_pairs(pairs([1.10] * 8), POLICY, "confirm")
    assert result["verdict"] == "confirmed_gain"
    assert result["alpha_one_sided"] == pytest.approx(0.05 / 3)
    assert result["lower_ratio_bound"] == pytest.approx(1.10)
    assert result["median_ratio"] == pytest.approx(1.10)


def test_exact_null_enumeration_respects_allocated_false_gain_rate():
    # Enumerate every equally likely independent fair sign pattern (no Monte
    # Carlo tolerance). This verifies nominal inference, not GPU noise models.
    policy = dict(POLICY, min_gain=0)
    for stage, alpha in (("confirm", 0.05 / 3), ("final", 0.05)):
        positives = sum(assess_pairs(pairs(signs), policy, stage)["verdict"] == "confirmed_gain"
                        for signs in itertools.product((0.9, 1.1), repeat=8))
        assert 0 < positives / 256 <= alpha
    assert assess_pairs(pairs([1] * 7 + [1000]), policy, "final")["verdict"] == "inconclusive"


@pytest.mark.parametrize("ratios,verdict", [
    ([1.2] * 8, "confirmed_gain"),
    ([0.8] * 8, "regression"),
    ([1] * 8, "inconclusive"),
    ([1.01] * 8, "inconclusive"),  # threshold equality never counts as a win
    ([0.98, 1.1] * 4, "inconclusive"),
    ([0.2] + [1.1] * 7, "inconclusive"),  # confirmation alpha is stricter
])
def test_paired_verdicts(ratios, verdict):
    assert assess_pairs(pairs(ratios), POLICY, "confirm")["verdict"] == verdict


def test_incomplete_and_invalid_samples_are_not_assessed():
    for bad in (pairs([1.1] * 7), pairs([1.1] * 9), pairs([1.1] * 7 + [math.nan]),
                pairs([1.1] * 7) + [{"reference": 100, "candidate": True}]):
        with pytest.raises(ValueError):
            assess_pairs(bad, POLICY, "confirm")


def test_extreme_finite_scores_keep_json_finite_and_log_evidence():
    result = assess_pairs([{"reference": 1e-300, "candidate": 1e300}] * 8, POLICY, "final")
    assert result["verdict"] == "confirmed_gain"
    assert result["lower_ratio_bound"] is None
    assert math.isfinite(result["lower_log_bound"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("changes", [
    {"method": "arbitrary"}, {"alpha": 0}, {"alpha": 0.5}, {"alpha": True},
    {"min_gain": -1}, {"min_gain": math.nan}, {"confirm_pairs": 7},
    {"final_pairs": 4}, {"confirm_pairs": 8.0}, {"max_confirmations": False},
    {"max_confirmations": 1025}, {"extra": 1},
])
def test_invalid_or_underpowered_policy_rejected(changes):
    with pytest.raises(ValueError):
        validate_policy(dict(POLICY, **changes))


@pytest.fixture
def ready(tmp_path):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=1,
                                eval_call_limit=128, final_eval_reserve=16,
                                protect_prefetch=False, comparison_policy=POLICY)
    obs = run.observe()
    candidate = prepare(run, obs)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    return run, candidate, obs


def test_policy_is_explicit_frozen_and_final_budget_is_reserved(tmp_path):
    run = RunController.create(tmp_path / "screen", _SYNTH, CONTRACT)
    assert_error("comparison_not_configured", lambda: run.confirm("normalized", FakeEvaluator()))
    assert_error("comparison_not_configured", lambda: run.finalize(FakeEvaluator()))
    with pytest.raises(ValueError, match="reserve"):
        RunController.create(tmp_path / "bad", _SYNTH, CONTRACT, comparison_policy=POLICY)
    assert not (tmp_path / "bad").exists()
    policy = dict(POLICY)
    run = RunController.create(tmp_path / "frozen", _SYNTH, CONTRACT,
                                final_eval_reserve=16, comparison_policy=policy)
    policy["min_gain"] = 0
    assert run.status()["manifest"]["comparison_policy"]["min_gain"] == 0.01


def test_confirm_uses_fresh_balanced_pairs_and_promotes_atomically(ready):
    run, candidate, obs = ready
    fake = evaluator()
    comparison = run.confirm(candidate, fake, evaluation_contract=CONTRACT)
    assert comparison["status"] == "completed"
    assert comparison["reference_id"] == "original"
    assert comparison["verdict"] == "confirmed_gain"
    assert len(fake.calls) == 16
    original = run.source("original").encode()
    modified = run.source(candidate).encode()
    assert fake.calls == [original, modified, modified, original] * 4
    state = RunController(run.directory).status()["state"]
    assert state["used"]["eval_calls"] == 18
    assert state["confirmation_count"] == 1
    assert state["incumbent_id"] == state["exploration_parent_id"] == candidate
    assert state["incumbent_evidence_id"] == comparison["id"]
    assert state["final_result"] is None
    assert_error("stale_observation", lambda: prepare(run, obs))
    for pair in comparison["pairs"]:
        for role in pair["order"]:
            batch = state["batches"][pair["batches"][role]]
            assert batch["stage"] == "confirm"
            attempt = state["attempts"][batch["attempt_ids"][0]]
            assert attempt["comparison_id"] == comparison["id"]
            assert attempt["role"] == role
            assert attempt["pair_index"] == pair["index"]
    # Comparison samples never replace the screening cache.
    cached_screen = run.evaluate(candidate, FakeEvaluator())
    assert cached_screen["stage"] == "screen" and cached_screen["cached"]
    assert run.confirm(candidate, fake)["cached"]
    assert len(fake.calls) == 16


def test_pair_order_bias_and_single_spike_cannot_promote(ready):
    run, candidate, _ = ready
    fake = FakeEvaluator(*(passed(x) for x in [100, 110] * 8))
    assert run.confirm(candidate, fake)["verdict"] == "inconclusive"
    assert run.status()["state"]["incumbent_id"] is None
    assert run.confirm(candidate, evaluator(candidate=200))["cached"]
    assert run.status()["state"]["confirmation_count"] == 1


def test_incumbent_is_next_reference_and_failed_challenger_does_not_replace_it(ready):
    run, first, _ = ready
    run.confirm(first, evaluator())
    second = prepare(run, spec={"kind": "layout", "layout": {"1": [8]}})["candidate_id"]
    run.evaluate(second, FakeEvaluator())
    result = run.confirm(second, evaluator(reference=110, candidate=100))
    assert result["reference_id"] == first
    assert result["verdict"] == "regression"
    state = run.status()["state"]
    assert state["incumbent_id"] == first
    assert state["confirmation_status"] == "confirmed_gain"
    assert run.select_parent(second)["incumbent_id"] == first


def test_original_cannot_be_promoted_back_into_a_final_self_comparison(ready):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    fake = evaluator(reference=110, candidate=120)
    assert_error("identical_candidate", lambda: run.confirm("original", fake))
    assert not fake.calls
    assert run.status()["state"]["incumbent_id"] == candidate


@pytest.mark.parametrize("bad,status", [
    (EvalResult(compiled=False), "compile_failed"),
    (EvalResult(compiled=True, correct=False), "incorrect"),
    (EvalResult(compiled=True, tflops=100), "measurement_invalid"),
    (RuntimeError("lost client"), "measurement_invalid"),
])
def test_any_failed_side_stops_comparison_and_records_which_side(ready, bad, status):
    run, candidate, _ = ready
    fake = FakeEvaluator(passed(), bad)
    comparison = run.confirm(candidate, fake)
    assert comparison["status"] == "measurement_failed"
    assert comparison["failure_status"] == status
    assert comparison["analysis"] is None
    state = run.status()["state"]
    assert state["batches"][comparison["failed_batch_id"]]["role"] == "candidate"
    assert state["incumbent_id"] is None
    assert state["used"]["eval_calls"] == 4
    assert run.confirm(candidate, evaluator())["cached"]
    assert state["confirmation_count"] == 1


def test_comparison_requires_latest_screen_and_matching_contract(ready):
    run, candidate, _ = ready
    fake = evaluator()
    assert_error("contract_mismatch", lambda: run.confirm(candidate, fake, evaluation_contract={}))
    run.evaluate(candidate, FakeEvaluator(EvalResult(compiled=False)), repeat=True)
    assert_error("screen_required", lambda: run.confirm(candidate, fake))
    assert not fake.calls


def test_identical_bytes_cannot_get_confirmed_from_measurement_noise(tmp_path):
    normalized, ok = run_module.driver.build_candidate(_SYNTH, {"kind": "ladder", "level": 1})
    assert ok
    run = RunController.create(tmp_path / "run", normalized, CONTRACT, perf_repeats=1,
                                final_eval_reserve=16, comparison_policy=POLICY)
    run.evaluate("original", FakeEvaluator())
    run.evaluate("normalized", FakeEvaluator())
    assert run.source("original") == run.source("normalized")
    assert_error("identical_candidate", lambda: run.confirm("normalized", evaluator()))


def test_confirmation_limit_and_whole_operation_budget(tmp_path):
    policy = dict(POLICY, max_confirmations=1)
    run = RunController.create(tmp_path / "limited", _SYNTH, CONTRACT, perf_repeats=1,
                                eval_call_limit=128, final_eval_reserve=16, comparison_policy=policy)
    first = prepare(run)["candidate_id"]
    second = prepare(run, spec={"kind": "layout", "layout": {"1": [8]}})["candidate_id"]
    for name in ("original", first, second):
        run.evaluate(name, FakeEvaluator())
    run.confirm(first, evaluator(candidate=99))
    assert_error("confirmation_budget_exhausted", lambda: run.confirm(second, evaluator()))
    limited = RunController.create(tmp_path / "budget", _SYNTH, CONTRACT, perf_repeats=1,
                                    eval_call_limit=33, final_eval_reserve=16, comparison_policy=POLICY)
    candidate = prepare(limited)["candidate_id"]
    limited.evaluate("original", FakeEvaluator())
    limited.evaluate(candidate, FakeEvaluator())
    assert_error("eval_budget_exhausted", lambda: limited.confirm(candidate, evaluator()))
    assert limited.status()["state"]["confirmation_count"] == 0


def test_interrupted_confirmation_keeps_charge_and_never_resumes_a_partial_test(ready):
    run, candidate, _ = ready
    with pytest.raises(KeyboardInterrupt):
        run.confirm(candidate, FakeEvaluator(passed(), KeyboardInterrupt()))
    state = run.status()["state"]
    assert state["used"]["eval_calls"] == 4
    assert state["incumbent_id"] is None
    assert_error("recovery_required", lambda: run.confirm(candidate, evaluator()))
    run.resume()
    fake = evaluator()
    comparison = RunController(run.directory).confirm(candidate, fake)
    assert comparison["status"] == "interrupted" and comparison["cached"]
    assert not fake.calls
    assert run.status()["state"]["confirmation_count"] == 1


def test_final_uses_protected_budget_new_samples_and_closes_run(tmp_path):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=1,
                                eval_call_limit=34, final_eval_reserve=16, comparison_policy=POLICY)
    candidate = prepare(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    confirmation = run.confirm(candidate, evaluator())
    assert_error("eval_budget_exhausted", lambda: run.evaluate(candidate, FakeEvaluator(), repeat=True))
    fake = evaluator("final", candidate=120)
    final = run.finalize(fake)
    assert final["status"] == "final_recommended"
    assert final["recommendation_id"] == candidate
    assert final["comparison_id"] != confirmation["id"]
    assert len(fake.calls) == 16
    state = run.status()["state"]
    assert state["used"]["eval_calls"] == 34
    assert state["phase"] == "finished"
    final_comparison = state["comparisons"][final["comparison_id"]]
    assert final_comparison["reference_id"] == "original"
    assert final_comparison["analysis"]["median_ratio"] == pytest.approx(1.2)
    assert run.finalize(fake)["cached"]
    assert len(fake.calls) == 16
    assert_error("run_closed", lambda: run.confirm(candidate, evaluator()))
    assert_error("run_closed", lambda: run.evaluate(candidate, FakeEvaluator()))
    assert_error("run_closed", lambda: prepare(run))


@pytest.mark.parametrize("fake", [evaluator("final", candidate=100),
                                  FakeEvaluator(EvalResult(compiled=True, correct=False))])
def test_final_failure_retains_original_without_claiming_it_was_revalidated(ready, fake):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    final = run.finalize(fake)
    assert final["status"] == "original_retained"
    assert final["recommendation_id"] is None
    assert final["selected_id"] == final["fallback_id"] == "original"
    assert final["selected_artifact"] == run.status()["state"]["candidates"]["original"]["artifact"]
    assert run.finalize(evaluator("final", candidate=200))["cached"]


def test_final_without_incumbent_finishes_without_hardware(ready):
    run, _, _ = ready
    fake = evaluator("final")
    final = run.finalize(fake)
    assert final["reason"] == "no_confirmed_candidate"
    assert final["comparison_id"] is None
    assert not fake.calls
    assert run.status()["state"]["phase"] == "finished"


def test_process_death_during_final_leaves_recoverable_evidence_and_no_recommendation(ready):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    code = """
import os, sys
from agent.run import RunController
from harness.evaluator import EvalResult
class Dies:
    calls = 0
    def evaluate(self, path, with_counters=False):
        self.calls += 1
        if self.calls == 2:
            os._exit(9)
        return EvalResult(compiled=True, correct=True, tflops=100)
RunController(sys.argv[1]).finalize(Dies())
"""
    process = subprocess.run([sys.executable, "-c", code, str(run.directory)],
                             cwd=str(run_module.REPO), capture_output=True, text=True)
    assert process.returncode == 9, process.stderr
    state = run.status()["state"]
    assert state["phase"] == "finalizing"
    assert state["final_result"] is None
    assert state["used"]["eval_calls"] == 20
    assert_error("recovery_required", lambda: run.finalize(evaluator("final")))
    recovery = RunController(run.directory).resume()
    assert recovery["phase"] == "finished"
    assert recovery["final_result"]["reason"] == "interrupted"
    assert recovery["final_result"]["recommendation_id"] is None
    assert recovery["used"]["eval_calls"] == 20
    assert run.finalize(evaluator("final"))["cached"]


def test_deadline_after_confirmation_finalizes_with_fallback(ready, monkeypatch):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    def expired(manifest):
        raise run_module.RunError("wall_time_exhausted", "expired")
    monkeypatch.setattr(run, "_check_deadline", expired)
    fake = evaluator("final")
    assert run.finalize(fake)["reason"] == "wall_time_exhausted"
    assert not fake.calls


def test_successive_promotions_finally_compare_against_original(ready):
    run, first, _ = ready
    run.confirm(first, evaluator())
    second = prepare(run, spec={"kind": "layout", "layout": {"1": [8]}})["candidate_id"]
    run.evaluate(second, FakeEvaluator())
    assert run.confirm(second, evaluator(reference=110, candidate=120))["reference_id"] == first
    final = run.finalize(evaluator("final", reference=100, candidate=120))
    comparison = run.status()["state"]["comparisons"][final["comparison_id"]]
    assert comparison["reference_id"] == "original"
    assert final["recommendation_id"] == second
    assert comparison["analysis"]["median_ratio"] == pytest.approx(1.2)


def test_a_failed_last_call_does_not_turn_a_promising_prefix_into_confirmation(ready):
    run, candidate, _ = ready
    fake = evaluator()
    fake.results[-1] = EvalResult(compiled=True, correct=False)
    result = run.confirm(candidate, fake)
    assert len(fake.calls) == 16
    assert result["analysis"] is None
    assert result["failure_status"] == "incorrect"
    assert run.status()["state"]["incumbent_id"] is None


def test_final_source_mutation_fails_without_modifying_archived_input(ready):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    class Mutates:
        def evaluate(self, path, with_counters=False):
            Path(path).write_text("unexpected client rewrite")
            return passed(200)
    result = run.finalize(Mutates())
    assert result["status"] == "original_retained"
    assert result["reason"] == "measurement_invalid"
    assert run.source("original") == _SYNTH


def test_final_recovery_does_not_infer_a_verdict_from_uncommitted_full_samples(ready, monkeypatch):
    run, candidate, _ = ready
    run.confirm(candidate, evaluator())
    def interrupted(*args):
        raise KeyboardInterrupt()
    with monkeypatch.context() as m:
        m.setattr(run_module, "assess_pairs", interrupted)
        with pytest.raises(KeyboardInterrupt):
            run.finalize(evaluator("final"))
    assert run.status()["state"]["used"]["eval_calls"] == 34
    result = run.resume()["final_result"]
    assert result["reason"] == "interrupted"
    assert result["recommendation_id"] is None


def test_mid_call_environment_change_preserves_raw_sample_but_blocks_promotion(ready, monkeypatch):
    run, candidate, _ = ready
    class ChangesSettings:
        def evaluate(self, path, with_counters=False):
            monkeypatch.setenv("ROCM_LLVM_BIN", "changed")
            return passed(200)
    result = run.confirm(candidate, ChangesSettings())
    assert result["failure_status"] == "measurement_invalid"
    state = run.status()["state"]
    batch = state["batches"][result["failed_batch_id"]]
    assert state["attempts"][batch["attempt_ids"][0]]["result"]["tflops"] == 200
    assert state["incumbent_id"] is None


def test_schema_one_remains_readable_but_cannot_be_modified(ready):
    run, _, _ = ready
    status = run.status()
    manifest, state = status["manifest"], status["state"]
    manifest["schema_version"] = state["schema_version"] = 1
    state["manifest_sha256"] = run_module._digest(manifest)
    (run.directory / "manifest.json").write_text(json.dumps(manifest))
    (run.directory / "state.json").write_text(json.dumps(state))
    assert run.status()["manifest"]["schema_version"] == 1
    assert_error("schema_upgrade_required", run.observe)
    assert_error("schema_upgrade_required", run.resume)


def test_cli_confirmation_and_final_use_frozen_policy_and_fresh_client_objects(cli, tmp_path):
    invoke, seed, cl, fake, _ = cli
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(POLICY))
    directory = invoke("init", str(seed), "--client", "fake/case", "--perf-repeats", "1",
                       "--eval-calls", "40", "--final-reserve", "16",
                       "--comparison-policy", str(policy_file))["run_dir"]
    run = RunController(directory)
    candidate = prepare(run)["candidate_id"]
    invoke("eval", directory, "original")
    invoke("eval", directory, candidate)
    fake.results = evaluator().results
    assert invoke("confirm", directory, candidate)["verdict"] == "confirmed_gain"
    assert cl.make_evaluator.call_count == 18
    fake.results = evaluator("final").results
    assert invoke("final", directory)["status"] == "final_recommended"
    assert cl.make_evaluator.call_count == 34
    assert invoke("final", directory)["cached"]
    assert cl.make_evaluator.call_count == 34
    assert invoke("confirm", directory, candidate, "--repeat", expected=2)["error"]["code"] == "arguments"
