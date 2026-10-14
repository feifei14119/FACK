"""Predeclared sequential looks and the signed-rank statistic, entirely on CPU."""
import itertools
import json
import math
import random

import pytest

from agent import history
from agent.run import RunController
from harness.comparison import (assess_look, assess_pairs, pair_order, signed_rank_lower_rank,
                                validate_policy)
from tools import tune_run_report
from unittests.test_session import _SYNTH
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, assert_error, passed, prepare

LOOKS = [{"pairs": 8, "alpha_share": 0.25}, {"pairs": 16, "alpha_share": 0.25},
         {"pairs": 32, "alpha_share": 0.5}]
POLICY = {"method": "paired_sequential_v1", "statistic": "signed_rank",
          "confirm_looks": LOOKS, "final_looks": LOOKS, "min_gain": 0.01,
          "alpha": 0.05, "max_confirmations": 3, "futility_stop": True}
SMALL_GAIN = [math.exp(0.02 + (-0.04, 0.04, -0.02, 0.02)[i % 4]) for i in range(32)]


def pairs(ratios):
    return [{"reference": 100, "candidate": 100 * r} for r in ratios]


def evaluator(ratios):
    scores = []
    for i, ratio in enumerate(ratios):
        for role in pair_order(i):
            scores.append(passed(100 * ratio if role == "candidate" else 100))
    return FakeEvaluator(*scores)


def test_signed_rank_bounds_match_published_critical_values():
    # Hollander & Wolfe: two-sided 95% intervals use the 9th (n=10) and 53rd
    # (n=20) Walsh averages, i.e. one-sided alpha 0.025.
    assert signed_rank_lower_rank(10, 0.025) == 9
    assert signed_rank_lower_rank(20, 0.025) == 53
    assert signed_rank_lower_rank(8, 2 ** -8) == 1
    assert signed_rank_lower_rank(8, 2 ** -8 * 0.99) == 0


def test_exact_null_enumeration_of_one_signed_rank_look():
    # Distinct magnitudes, every equally likely sign pattern: no Monte Carlo tolerance.
    policy = dict(POLICY, min_gain=0, futility_stop=False,
                  confirm_looks=[{"pairs": 10, "alpha_share": 1}])
    alpha = 0.05 / 3
    positives = 0
    for signs in itertools.product((-1, 1), repeat=10):
        ratios = [math.exp(s * 0.01 * (k + 1)) for k, s in enumerate(signs)]
        positives += assess_pairs(pairs(ratios), policy, "confirm")["verdict"] == "confirmed_gain"
    assert 0 < positives / 1024 <= alpha


@pytest.mark.parametrize("statistic", ["sign", "signed_rank"])
def test_repeated_looks_keep_false_gains_within_stage_alpha(statistic):
    policy = dict(POLICY, statistic=statistic, min_gain=0, futility_stop=False)
    rng = random.Random(7)
    trials, gains = 1500, 0
    for _ in range(trials):
        ratios = [math.exp(rng.gauss(0, 0.03)) for _ in range(32)]
        for index, n in enumerate((8, 16, 32)):
            look = assess_look(pairs(ratios[:n]), policy, "confirm", index)
            if look["stop"]:
                gains += look["verdict"] == "confirmed_gain"
                break
    assert gains / trials <= 0.05 / 3


@pytest.mark.parametrize("ratios,pairs_used,verdict,reason", [
    ([1.10] * 32, 8, "confirmed_gain", "confirmed_gain"),
    ([0.90] * 32, 8, "regression", "regression"),
    ([1.00] * 32, 8, "inconclusive", "futility"),
    (SMALL_GAIN, 32, "confirmed_gain", "confirmed_gain"),
])
def test_large_effects_stop_early_and_small_gains_use_every_look(ratios, pairs_used, verdict, reason):
    for index, n in enumerate((8, 16, 32)):
        look = assess_look(pairs(ratios[:n]), POLICY, "confirm", index)
        if look["stop"]:
            break
    assert (look["pairs"], look["verdict"], look["stop_reason"]) == (pairs_used, verdict, reason)
    result = assess_pairs(pairs(ratios[:pairs_used]), POLICY, "confirm")
    assert result["verdict"] == verdict and result["planned_pairs"] == 32
    assert [entry["pairs"] for entry in result["looks"]] == [8, 16, 32][:len(result["looks"])]
    json.dumps(result, allow_nan=False)


def test_no_futility_stop_continues_to_the_last_look():
    policy = dict(POLICY, futility_stop=False)
    assert not assess_look(pairs([1.0] * 8), policy, "confirm", 0)["stop"]
    assert assess_pairs(pairs([1.0] * 32), policy, "confirm")["stop_reason"] == "max_pairs"


def test_samples_must_end_exactly_at_the_first_stopping_look():
    for bad in (pairs([1.10] * 16),          # continued past a decisive look
                pairs(SMALL_GAIN[:16]),      # truncated at a look that did not stop
                pairs(SMALL_GAIN[:20]),      # not a look at all
                pairs([1.10] * 7)):
        with pytest.raises(ValueError):
            assess_pairs(bad, POLICY, "confirm")


@pytest.mark.parametrize("changes", [
    {"statistic": "t_test"}, {"futility_stop": 1}, {"extra": 1}, {"alpha": 0.5},
    {"confirm_looks": []}, {"confirm_looks": [{"pairs": 8, "alpha_share": 0.5}]},
    {"confirm_looks": [{"pairs": 7, "alpha_share": 1}]},
    {"confirm_looks": [{"pairs": 16, "alpha_share": 0.5}, {"pairs": 8, "alpha_share": 0.5}]},
    {"confirm_looks": [{"pairs": 514, "alpha_share": 1}]},
    {"confirm_looks": [{"pairs": 4, "alpha_share": 0.5}, {"pairs": 32, "alpha_share": 0.5}]},
    {"confirm_looks": [{"pairs": 8, "alpha_share": 0}, {"pairs": 32, "alpha_share": 1}]},
    {"confirm_looks": [{"pairs": 8}]},
])
def test_invalid_or_underpowered_sequential_policy_rejected(changes):
    with pytest.raises(ValueError):
        validate_policy(dict(POLICY, **changes))


def make_run(tmp_path, eval_calls=200, reserve=64):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=1,
                                eval_call_limit=eval_calls, final_eval_reserve=reserve,
                                protect_prefetch=False, comparison_policy=POLICY)
    candidate = prepare(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    return run, candidate


def test_controller_stops_early_charges_only_measured_pairs_and_reserves_last_look(tmp_path):
    with pytest.raises(ValueError, match="reserve"):
        RunController.create(tmp_path / "bad", _SYNTH, CONTRACT, final_eval_reserve=32,
                             comparison_policy=POLICY)
    run, candidate = make_run(tmp_path)
    fake = evaluator([1.10] * 32)
    comparison = run.confirm(candidate, fake)
    assert comparison["verdict"] == "confirmed_gain"
    assert len(fake.calls) == 16 and len(comparison["pairs"]) == 8
    assert comparison["planned_pairs"] == 32
    assert run.status()["state"]["used"]["eval_calls"] == 2 + 16
    final_fake = evaluator(SMALL_GAIN)
    final = run.finalize(final_fake)
    assert final["status"] == "final_recommended"
    assert len(final_fake.calls) == 64
    state = run.status()["state"]
    final_comparison = state["comparisons"][final["comparison_id"]]
    assert final_comparison["analysis"]["stop_reason"] == "confirmed_gain"
    assert len(final_comparison["pairs"]) == 32
    for evidence in (comparison, final_comparison):
        history._comparison(run.status()["manifest"], state, state["comparisons"][evidence["id"]])
    exported = tune_run_report.export_report(run.directory)
    assert not exported["integrity_errors"]
    report = open(exported["markdown_path"], encoding="utf-8").read()
    assert "| confirm | {} | original | completed | confirmed_gain | 8 | 32 | confirmed_gain |".format(
        candidate) in report


def test_confirmation_needs_budget_for_the_last_look_even_if_it_may_stop_early(tmp_path):
    run, candidate = make_run(tmp_path, eval_calls=64 + 2 + 63)
    fake = evaluator([1.10] * 32)
    assert_error("eval_budget_exhausted", lambda: run.confirm(candidate, fake))
    assert not fake.calls


def test_history_rejects_sequential_evidence_that_ran_past_its_stop(tmp_path):
    run, candidate = make_run(tmp_path)
    comparison = run.confirm(candidate, evaluator([1.10] * 32))
    state = run.status()["state"]
    tampered = json.loads(json.dumps(state["comparisons"][comparison["id"]]))
    tampered["pairs"] = tampered["pairs"][:4]
    with pytest.raises(Exception, match="incomplete"):
        history._comparison(run.status()["manifest"], state, tampered)
