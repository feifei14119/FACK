"""Warm starts require complete provenance and never reuse client samples."""
import copy
import json

import pytest

from agent.history import HistoryError, candidate_chain, load_history
from agent.replay import verify_chain
from agent.run import RunController
from unittests.test_paired_validation import POLICY, evaluator
from unittests.test_session import _SYNTH, _loads
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, prepare


@pytest.fixture
def history(tmp_path):
    run = RunController.create(tmp_path / "history", _SYNTH, CONTRACT,
                               perf_repeats=1, protect_prefetch=False, eval_call_limit=64,
                               final_eval_reserve=16, comparison_policy=POLICY)
    run.evaluate("original", FakeEvaluator())
    candidate = prepare(run)["candidate_id"]
    run.evaluate(candidate, FakeEvaluator())
    run.confirm(candidate, evaluator())
    return run, candidate, run.status()["manifest"]


def mutate_state(run, change):
    path = run.directory / "state.json"
    state = json.loads(path.read_text())
    change(state)
    path.write_text(json.dumps(state))


def test_history_returns_rebuild_recipe_and_no_old_measurements(history):
    run, candidate, current = history
    before = (run.directory / "state.json").read_bytes()
    result = load_history(run.directory, current)
    assert result["candidate_id"] == candidate
    assert result["requires_evaluation"] is True
    assert result["measurements_imported"] is False
    assert "tflops" not in result and "measurement" not in result
    rebuilt = verify_chain(_SYNTH, result["chain"], current["build_policy"])
    assert rebuilt["source"] == run.source(candidate)
    assert (run.directory / "state.json").read_bytes() == before


def test_final_recommendation_requires_original_reference_evidence(history):
    run, candidate, current = history
    run.finalize(evaluator("final"))
    result = load_history(run.directory, current)
    assert result["candidate_id"] == candidate
    assert result["evidence_ref"]["stage"] == "final"
    mutate_state(run, lambda state: state["comparisons"][result["evidence_ref"]["comparison_id"]].update(
        reference_id=candidate))
    with pytest.raises(HistoryError):
        load_history(run.directory, current)


@pytest.mark.parametrize("field", ["original_sha256", "engine_identity", "runtime_identity",
                                   "evaluation_contract", "build_policy", "default_region", "schema_version"])
def test_history_requires_all_frozen_identity_fields(history, field):
    run, _, current = history
    incompatible = copy.deepcopy(current)
    incompatible[field] = "different"
    with pytest.raises(HistoryError) as exc:
        load_history(run.directory, incompatible)
    assert exc.value.code == "history_mismatch"
    del incompatible[field]
    with pytest.raises(HistoryError) as exc:
        load_history(run.directory, incompatible)
    assert exc.value.code == "history_mismatch"


def test_manifest_and_every_archived_artifact_are_checked(history):
    run, _, current = history
    path = run.directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["perf_repeats"] += 1
    path.write_text(json.dumps(manifest))
    with pytest.raises(HistoryError, match="manifest digest"):
        load_history(run.directory, current)
    path.write_text(json.dumps(current))
    state = run.status()["state"]
    artifact = run.directory / state["candidates"]["normalized"]["artifact"]["path"]
    artifact.write_text("arbitrary changed assembly")
    with pytest.raises(HistoryError, match="artifact digest"):
        load_history(run.directory, current)


@pytest.mark.parametrize("change", [
    lambda state: state["observations"].clear(),
    lambda state: state["proposals"].clear(),
    lambda state: next(iter(state["attempts"].values()))["result"].update(correct=False),
    lambda state: next(iter(state["comparisons"].values()))["pairs"][0]["scores"].update(candidate=999),
    lambda state: next(iter(state["comparisons"].values())).update(analysis={"verdict": "confirmed_gain"}),
    lambda state: next(iter(state["attempts"].values())).update(source_sha256="0" * 64),
])
def test_history_rejects_missing_or_inconsistent_reference_evidence(history, change):
    run, _, current = history
    mutate_state(run, change)
    with pytest.raises(HistoryError):
        load_history(run.directory, current)


def test_arbitrary_assembly_is_not_adopted_as_a_historical_intent(history):
    run, candidate, current = history
    mutate_state(run, lambda state: state["candidates"][candidate].update(spec=None))
    with pytest.raises(HistoryError, match="no constrained build recipe"):
        load_history(run.directory, current)


def test_candidate_and_proposal_region_cannot_rewrite_observation_scope(history):
    run, candidate, current = history
    state = run.status()["state"]
    state["candidates"][candidate]["spec"]["region"] = "body"
    for proposal in state["proposals"]:
        if proposal.get("candidate_id") == candidate:
            proposal["spec"]["region"] = "body"
            assert state["observations"][proposal["observation_id"]]["region"] == "loop"
    with pytest.raises(HistoryError, match="version-bound successful proposal"):
        candidate_chain(state, candidate, current["build_policy"])


def test_failed_final_does_not_become_warm_start_winner(history):
    run, _, current = history
    run.finalize(evaluator("final", candidate=90))
    with pytest.raises(HistoryError) as exc:
        load_history(run.directory, current)
    assert exc.value.code == "no_history_candidate"


def test_screening_only_candidate_is_not_a_historical_winner(history):
    run, candidate, current = history
    mutate_state(run, lambda state: state.update(incumbent_id=None, incumbent_evidence_id=None, comparisons={}))
    for selected in (None, candidate):
        with pytest.raises(HistoryError) as exc:
            load_history(run.directory, current, candidate_id=selected)
        assert exc.value.code == "no_history_candidate"


def test_ancestry_cycles_and_missing_parents_are_rejected(history):
    run, candidate, current = history
    state = run.status()["state"]
    state["candidates"][candidate]["parent_id"] = "missing"
    with pytest.raises(HistoryError, match="missing historical parent"):
        candidate_chain(state, candidate, current["build_policy"])


def test_candidate_path_cannot_escape_archive(history, tmp_path):
    run, candidate, current = history
    outside = tmp_path / "external.s"
    outside.write_text(run.source(candidate))
    mutate_state(run, lambda state: state["candidates"][candidate]["artifact"].update(path=str(outside)))
    with pytest.raises(HistoryError, match="outside the run"):
        load_history(run.directory, current)


def test_incumbent_reference_must_have_its_own_original_linked_confirmation(history):
    run, first, current = history
    candidate = prepare(run, spec={"kind": "layout", "layout": {"1": [_loads(run.source(first))[1][1]]}})["candidate_id"]
    run.evaluate(candidate, FakeEvaluator())
    run.confirm(candidate, evaluator())
    assert load_history(run.directory, current)["candidate_id"] == candidate
    def remove_reference_evidence(state):
        state["comparisons"] = {k: c for k, c in state["comparisons"].items() if c["candidate_id"] != first}
    mutate_state(run, remove_reference_evidence)
    with pytest.raises(HistoryError, match="reference has no prior confirmation"):
        load_history(run.directory, current)
