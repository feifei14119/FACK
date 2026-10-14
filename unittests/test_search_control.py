"""Persistent navigation budgets and profiling, using only fake CPU clients."""
import json
from pathlib import Path

import pytest

from agent.run import RunController
from agent.search_control import search_status
from harness.evaluator import EvalResult
from search import driver
from unittests.test_paired_validation import POLICY, evaluator
from unittests.test_session import _SYNTH, _loads
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, assert_error, cli, passed


def create(tmp_path, search_policy=None, paired=False, repeats=1, calls=100):
    return RunController.create(
        tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=repeats,
        protect_prefetch=False, eval_call_limit=calls,
        final_eval_reserve=16 if paired else 0,
        comparison_policy=POLICY if paired else None, search_policy=search_policy)


def usage(run):
    snapshot = run.status()
    return search_status(snapshot["manifest"], snapshot["state"])


def proposal(run, index=0, direction="memory_early"):
    obs = run.observe()
    spec = {"kind": "layout", "layout": {"0": [_loads(_SYNTH)[1][index]]}}
    return run.prepare(obs["observation_id"], obs["base_sha256"], spec,
                       hypothesis={"direction": direction, "source": "observation"})


class ProfileEvaluator:
    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else EvalResult(
            compiled=True, correct=True, tflops=9999,
            counters={"stall_cycles": 7}, direction={"bottleneck": "memory"})

    def evaluate(self, path, with_counters=False):
        assert with_counters is True
        self.calls.append(Path(path).read_bytes())
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_frozen_default_policy_disables_profile_without_spending(tmp_path):
    run = create(tmp_path)
    frozen = run.status()["manifest"]["search_policy"]
    assert frozen["profile_call_limit"] == 0
    assert frozen["direction_eval_call_limit"] is None
    run.evaluate("original", FakeEvaluator())
    fake = ProfileEvaluator()
    assert_error("profile_budget_exhausted", lambda: run.profile("original", fake))
    assert not fake.calls
    assert run.status()["state"]["used"]["eval_calls"] == 1
    assert usage(run)["profile_calls"] == 0


def test_suggest_creates_bound_observation_and_no_evaluation(tmp_path):
    run = create(tmp_path)
    before = run.status()["state"]["used"]
    result = run.suggest(n=4)
    obs = result["observation"]
    assert 1 <= len(result["suggestions"]) <= 4
    assert obs["base_sha256"] == run.status()["manifest"]["original_sha256"]
    assert run.status()["state"]["used"] == before
    choice = result["suggestions"][0]
    assert choice["hypothesis"]["direction"] == choice["direction"]
    assert choice["hypothesis"]["evidence_refs"] == [
        {"kind": "observation", "id": obs["observation_id"]}]
    result = run.prepare(obs["observation_id"], obs["base_sha256"], choice["spec"],
                         hypothesis=choice["hypothesis"])
    assert result["status"] == "prepared"
    assert run.status()["state"]["candidates"][result["candidate_id"]]["direction"] == choice["direction"]


def test_direction_cap_is_charged_per_call_and_cannot_be_renamed(tmp_path):
    run = create(tmp_path, {"direction_eval_call_limit": 2}, repeats=2)
    first = proposal(run)["candidate_id"]
    second = proposal(run, 1, "alu_late")["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(first, FakeEvaluator())
    assert usage(run)["direction_eval_calls"]["memory_early"] == 2
    duplicate = proposal(run, direction="another_direction")
    assert duplicate["candidate_id"] == first
    assert run.status()["state"]["candidates"][first]["direction"] == "memory_early"
    fake = FakeEvaluator()
    assert_error("direction_budget_exhausted", lambda: run.evaluate(first, fake, repeat=True))
    assert not fake.calls
    assert run.evaluate(second, FakeEvaluator())["status"] == "measured"
    assert usage(run)["direction_eval_calls"]["alu_late"] == 2


def test_direction_budget_checks_complete_repeat_batch_before_any_call(tmp_path):
    run = create(tmp_path, {"direction_eval_call_limit": 1}, repeats=2)
    candidate = proposal(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    fake = FakeEvaluator()
    assert_error("direction_budget_exhausted", lambda: run.evaluate(candidate, fake))
    assert not fake.calls
    assert run.status()["state"]["used"]["eval_calls"] == 2


def test_invalid_measurement_spends_direction_budget_but_not_stagnation(tmp_path):
    run = create(tmp_path, {"direction_eval_call_limit": 1, "stagnation_limit": 1})
    candidate = proposal(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    assert run.evaluate(candidate, FakeEvaluator(EvalResult(compiled=False)))["status"] == "compile_failed"
    assert usage(run)["direction_eval_calls"]["memory_early"] == 1
    assert usage(run)["stagnation_count"] == 0
    assert_error("direction_budget_exhausted", lambda: run.evaluate(candidate, FakeEvaluator(), repeat=True))


def test_stagnation_counts_unique_valid_screens_and_confirmation_resets_it(tmp_path):
    run = create(tmp_path, {"stagnation_limit": 2}, paired=True)
    first = proposal(run)["candidate_id"]
    second = proposal(run, 1)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(first, FakeEvaluator())
    assert usage(run)["stagnation_count"] == 1
    run.evaluate(first, FakeEvaluator(), repeat=True)
    assert usage(run)["stagnation_count"] == 1
    run.evaluate(second, FakeEvaluator())
    assert usage(run)["search_stopped"] is True
    assert_error("search_stagnated", lambda: proposal(run, 2))
    assert_error("search_stagnated", lambda: run.evaluate(first, FakeEvaluator(), repeat=True))
    result = run.confirm(first, evaluator())
    assert result["verdict"] == "confirmed_gain"
    assert usage(run)["stagnation_count"] == 0
    assert usage(run)["search_stopped"] is False
    assert run.suggest()["observation"]["parent_id"] == first


def test_stagnation_does_not_block_final_fallback(tmp_path):
    run = create(tmp_path, {"stagnation_limit": 1}, paired=True)
    candidate = proposal(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    assert usage(run)["search_stopped"] is True
    result = run.finalize(FakeEvaluator())
    assert result["status"] == "original_retained"


def test_profile_spends_both_budgets_and_cannot_replace_screen_samples(tmp_path):
    run = create(tmp_path, {"profile_call_limit": 1})
    original = run.evaluate("original", FakeEvaluator(passed(100)))
    fake = ProfileEvaluator()
    profile = run.profile("original", fake)
    assert len(fake.calls) == 1
    assert profile["stage"] == "profile" and profile["profile_status"] == "available"
    assert profile["measurement"]["tflops"] == 9999
    status = run.status()["state"]
    assert status["used"]["eval_calls"] == 2
    assert usage(run)["profile_calls"] == 1
    assert usage(run)["current_profile_id"] == profile["id"]
    cached = run.evaluate("original", FakeEvaluator())
    assert cached["id"] == original["id"] and cached["measurement"]["tflops"] == 100
    assert_error("profile_budget_exhausted", lambda: run.profile("original", ProfileEvaluator()))


def test_explicit_unlimited_profile_policy_and_missing_counters(tmp_path):
    run = create(tmp_path, {"profile_call_limit": None})
    run.evaluate("original", FakeEvaluator())
    profile = run.profile("original", ProfileEvaluator(passed(123)))
    assert profile["profile_status"] == "unavailable"
    assert usage(run)["profile_needs_refresh"] is True
    run.profile("original", ProfileEvaluator())
    assert usage(run)["profile_calls"] == 2
    assert usage(run)["profile_needs_refresh"] is False


def test_profile_requires_screening_and_profile_is_invalidated_by_promotion(tmp_path):
    run = create(tmp_path, {"profile_call_limit": 2}, paired=True)
    candidate = proposal(run)["candidate_id"]
    assert_error("screen_required", lambda: run.profile(candidate, ProfileEvaluator()))
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    old = run.profile("original", ProfileEvaluator())
    assert usage(run)["current_profile_id"] == old["id"]
    run.confirm(candidate, evaluator())
    assert usage(run)["profile_needs_refresh"] is True
    current = run.profile(candidate, ProfileEvaluator())
    assert usage(run)["current_profile_id"] == current["id"]
    state = run.status()["state"]
    comparison = next(iter(state["comparisons"].values()))
    comparison_batches = {p["batches"][side] for p in comparison["pairs"] for side in ("reference", "candidate")}
    assert old["id"] not in comparison_batches and current["id"] not in comparison_batches


def test_interrupted_profile_remains_charged_after_explicit_recovery(tmp_path):
    run = create(tmp_path, {"profile_call_limit": 1})
    run.evaluate("original", FakeEvaluator())
    with pytest.raises(KeyboardInterrupt):
        run.profile("original", ProfileEvaluator(KeyboardInterrupt()))
    assert usage(run)["profile_calls"] == 1
    assert run.status()["state"]["used"]["eval_calls"] == 2
    run.resume()
    assert_error("profile_budget_exhausted", lambda: run.profile("original", ProfileEvaluator()))
    assert usage(run)["profile_calls"] == 1


def test_profile_cannot_consume_reserved_independent_search_calls(tmp_path):
    run = create(tmp_path, {"profile_call_limit": 3, "independent_eval_reserve": 2}, calls=4)
    candidate = proposal(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.profile("original", ProfileEvaluator())
    assert usage(run)["independent_eval_calls"] == 0
    assert_error("independent_reserve", lambda: run.profile("original", ProfileEvaluator()))
    assert run.evaluate(candidate, FakeEvaluator())["status"] == "measured"
    assert usage(run)["independent_eval_calls"] == 1


def test_normalized_with_original_bytes_does_not_count_as_stagnation(tmp_path):
    normalized, ok = driver.build_candidate(_SYNTH, {"kind": "ladder", "level": 1,
                                                   "opt_level": 1, "protect_prefetch": False})
    assert ok
    run = RunController.create(tmp_path / "run", normalized, CONTRACT, perf_repeats=1,
                                protect_prefetch=False, search_policy={"stagnation_limit": 1})
    state = run.status()["state"]
    assert state["candidates"]["normalized"]["artifact"]["sha256"] == state["candidates"]["original"]["artifact"]["sha256"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate("normalized", FakeEvaluator())
    assert usage(run)["stagnation_count"] == 0
    assert usage(run)["search_stopped"] is False


def test_legacy_records_without_stage_remain_readable(tmp_path):
    run = create(tmp_path)
    candidate = proposal(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    snapshot = run.status()
    expected = search_status(snapshot["manifest"], snapshot["state"])
    # Historical P0-b records predate explicit screen/confirm/profile stages.
    for table in ("attempts", "batches"):
        for item in snapshot["state"][table].values():
            del item["stage"]
    assert search_status(snapshot["manifest"], snapshot["state"]) == expected


def test_cli_search_policy_suggest_hypothesis_eval_profile_and_ledger(cli, tmp_path):
    invoke, seed, cl, _, _ = cli

    class ModeRecordingClient:
        def __init__(self):
            self.modes = []

        def evaluate(self, path, with_counters=False):
            assert Path(path).is_file()
            self.modes.append(with_counters)
            return EvalResult(compiled=True, correct=True,
                              tflops=9999 if with_counters else 100,
                              counters={"stall_cycles": 7} if with_counters else None)

    fake = ModeRecordingClient()
    cl.make_evaluator.return_value = fake
    policy = tmp_path / "search-policy.json"
    policy.write_text(json.dumps({"profile_call_limit": 1, "direction_eval_call_limit": 2,
                                  "independent_eval_reserve": 1}))
    params = ["shape=1", "shape=2", "--check", "a b"]
    initialized = invoke("init", str(seed), "--client", "fake/case", "--run-id", "search-cli",
                         "--search-policy", str(policy), "--no-protect-prefetch",
                         "--perf-repeats", "1", "--eval-calls", "8", "--", *params)
    directory = initialized["run_dir"]
    assert initialized["manifest"]["search_policy"]["profile_call_limit"] == 1
    policy.write_text(json.dumps({"profile_call_limit": 0}))
    suggested = invoke("suggest", directory, "--n", "3")
    obs, choice = suggested["observation"], suggested["suggestions"][0]
    spec, hypothesis = tmp_path / "spec.json", tmp_path / "hypothesis.json"
    spec.write_text(json.dumps(choice["spec"]))
    hypothesis.write_text(json.dumps(choice["hypothesis"]))
    prepared = invoke("prepare", directory, "--observation", obs["observation_id"],
                      "--base-sha256", obs["base_sha256"], "--spec-file", str(spec),
                      "--hypothesis-file", str(hypothesis))
    candidate = prepared["candidate_id"]
    assert not cl.make_evaluator.called and not fake.modes
    assert invoke("eval", directory, "original")["status"] == "measured"
    screen = invoke("eval", directory, candidate)
    profile = invoke("profile", directory, candidate)
    assert profile["stage"] == "profile" and profile["profile_status"] == "available"
    assert fake.modes == [False, False, True]
    assert cl.make_evaluator.call_args.kwargs["params"] == params
    assert invoke("eval", directory, candidate)["id"] == screen["id"]
    assert fake.modes == [False, False, True]  # profile did not replace the screen cache
    status = invoke("status", directory)
    assert status["state"]["used"]["eval_calls"] == 3
    assert status["search"]["profile_calls"] == 1
    assert status["manifest"]["search_policy"]["profile_call_limit"] == 1
    ledger = invoke("ledger", directory)
    row = next(row for row in ledger["rows"] if row["id"] == prepared["id"])
    assert row["hypothesis"] == choice["hypothesis"]
    assert {batch["stage"] for batch in row["batches"]} == {"screen", "profile"}


def test_small_suggestion_request_rotates_past_exhausted_direction(tmp_path):
    run = create(tmp_path, {"direction_eval_call_limit": 1})
    suggestion = run.suggest(n=4)
    choice = suggestion["suggestions"][0]
    obs = suggestion["observation"]
    candidate = run.prepare(obs["observation_id"], obs["base_sha256"], choice["spec"],
                            hypothesis=choice["hypothesis"])["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    next_choices = run.suggest(n=1)["suggestions"]
    assert all(c["direction"] != choice["direction"] for c in next_choices)


def test_suggestions_stop_at_wall_deadline_without_new_observation(tmp_path, monkeypatch):
    from agent import run as run_module
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT,
                                protect_prefetch=False, wall_time_limit=30)
    before = run.status()
    monkeypatch.setattr(run_module.time, "time", lambda: before["manifest"]["created_at"] + 31)
    assert_error("wall_time_exhausted", lambda: run.suggest(n=1))
    assert run.status()["state"]["observations"] == before["state"]["observations"]
