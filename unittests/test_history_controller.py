"""Current-run history imports use CPU gates and never adopt old measurements."""
import copy
import os

import pytest

from agent import run as run_module
from agent.history import HistoryError, load_history
from agent.history_controller import HistoryControllerMixin
from agent.run import RunController
from unittests.test_paired_validation import POLICY, evaluator
from unittests.test_run_history import mutate_state
from unittests.test_session import _SYNTH, _loads
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, assert_error, prepare


class Controller(RunController, HistoryControllerMixin):
    """Exercise integration hooks before/after the main controller inherits it."""


def create(directory, source=_SYNTH, **kwargs):
    return Controller.create(directory, source, CONTRACT, perf_repeats=1,
                             protect_prefetch=False, eval_call_limit=160,
                             final_eval_reserve=16, comparison_policy=POLICY, **kwargs)


@pytest.fixture
def history_chain(tmp_path):
    history = create(tmp_path / "history")
    history.evaluate("original", FakeEvaluator())
    first = prepare(history)["candidate_id"]
    history.evaluate(first, FakeEvaluator())
    history.confirm(first, evaluator())
    second = prepare(history, spec={"kind": "layout", "layout": {
        "1": [_loads(history.source(first))[1][1]]}})["candidate_id"]
    assert first != second
    history.evaluate(second, FakeEvaluator())
    history.confirm(second, evaluator())
    return history, first, second


def selection(state):
    return {key: copy.deepcopy(state[key]) for key in (
        "exploration_parent_id", "parent_revision", "incumbent_id", "incumbent_evidence_id",
        "confirmation_status", "confirmation_count", "final_result", "phase")}


def assert_unmeasured(state):
    assert state["attempts"] == state["batches"] == state["comparisons"] == {}
    assert state["used"]["eval_calls"] == 0
    assert state["incumbent_id"] is None


def proposal_for(state, proposal_id):
    return next(item for item in state["proposals"] if item["id"] == proposal_id)


def test_history_reads_verified_recipe_without_mutating_either_run(tmp_path, history_chain):
    history, _, second = history_chain
    run = create(tmp_path / "current")
    before = [(item.directory / "state.json").read_bytes() for item in (run, history)]
    recipe = run.history(history.directory)
    assert recipe["candidate_id"] == second
    assert len(recipe["chain"]) == 2
    assert recipe["requires_evaluation"] and not recipe["measurements_imported"]
    assert before == [(item.directory / "state.json").read_bytes() for item in (run, history)]


@pytest.mark.parametrize("operation", ["history", "warm_start"])
def test_history_checks_current_engine_before_using_frozen_manifest(tmp_path, history_chain, monkeypatch, operation):
    history, _, _ = history_chain
    run = create(tmp_path / "current")
    before = (run.directory / "state.json").read_bytes()
    monkeypatch.setattr(run_module, "engine_identity", lambda: "changed")
    assert_error("environment_changed", lambda: getattr(run, operation)(history.directory))
    assert (run.directory / "state.json").read_bytes() == before


def test_warm_start_registers_complete_chain_with_provenance_and_request_cost(tmp_path, history_chain):
    history, first, second = history_chain
    history_before = (history.directory / "state.json").read_bytes()
    run = create(tmp_path / "current")
    before = selection(run.status()["state"])
    action = run.warm_start(history.directory)
    state = run.status()["state"]
    assert action["status"] == "prepared"
    assert action["candidate_id"] == second
    assert len(action["registered"]) == 2
    assert run.source(second) == history.source(second)
    assert state["used"]["proposals"] == 3  # one request plus two steps
    assert run.status()["search"]["reuse_proposals"] == 3
    assert selection(state) == before
    assert_unmeasured(state)
    request = proposal_for(state, action["request_proposal_id"])
    assert request["status"] == "import_prepared"
    assert request["reuse"] and request["reuse_charged"]
    assert request["provenance"]["source_evidence_ref"] == action["source_evidence_ref"]
    for index, item in enumerate(action["registered"]):
        proposal = proposal_for(state, item["proposal_id"])
        assert proposal["detached"] and proposal["reuse"] and proposal["reuse_charged"]
        assert proposal["parent_id"] == ("original" if index == 0 else first)
        assert proposal["provenance"] == {
            "import_id": action["id"], "step_index": index,
            "source_evidence_ref": action["source_evidence_ref"]}
        assert state["candidates"][item["candidate_id"]]["reuse"]
        observation = state["observations"][proposal["observation_id"]]
        assert observation["parent_revision"] == before["parent_revision"]
        assert observation["parent_id"] == proposal["parent_id"]
    assert (history.directory / "state.json").read_bytes() == history_before


def test_detached_import_preserves_current_incumbent_parent_and_samples(tmp_path, history_chain):
    history, _, _ = history_chain
    run = create(tmp_path / "current")
    run.evaluate("original", FakeEvaluator())
    independent = prepare(run, spec={"kind": "layout", "layout": {"1": [_loads(_SYNTH)[1][0]]}})["candidate_id"]
    run.evaluate(independent, FakeEvaluator())
    run.confirm(independent, evaluator())
    before = run.status()["state"]
    run.warm_start(history.directory)
    after = run.status()["state"]
    assert selection(after) == selection(before)
    assert after["exploration_parent_id"] == independent
    for key in ("batches", "attempts", "comparisons"):
        assert after[key] == before[key]
    assert after["used"]["eval_calls"] == before["used"]["eval_calls"]


def test_import_still_requires_current_baseline_screen_and_confirmation(tmp_path, history_chain):
    history, _, _ = history_chain
    run = create(tmp_path / "current")
    candidate = run.warm_start(history.directory)["candidate_id"]
    fake = FakeEvaluator()
    assert_error("baseline_required", lambda: run.evaluate(candidate, fake))
    assert_error("screen_required", lambda: run.confirm(candidate, evaluator()))
    assert not fake.calls
    run.evaluate("original", fake)
    run.evaluate(candidate, fake)
    assert run.status()["state"]["incumbent_id"] is None
    assert run.confirm(candidate, evaluator())["verdict"] == "confirmed_gain"
    assert run.status()["state"]["incumbent_id"] == candidate
    assert run.status()["search"]["reuse_eval_calls"] == 1 + POLICY["confirm_pairs"]


@pytest.mark.parametrize("limit,code", [
    ({"search_policy": {"reuse_proposal_limit": 2}}, "reuse_proposal_budget_exhausted"),
    ({"proposal_limit": 2}, "proposal_budget_exhausted"),
])
def test_partial_import_keeps_registered_steps_when_proposal_budget_runs_out(tmp_path, history_chain, limit, code):
    history, first, second = history_chain
    run = create(tmp_path / "current", **limit)
    before = selection(run.status()["state"])
    assert_error(code, lambda: run.warm_start(history.directory))
    state = run.status()["state"]
    action = state["imports"][0]
    assert action["status"] == "rejected" and action["error_code"] == code
    assert [item["candidate_id"] for item in action["registered"]] == [first]
    assert first in state["candidates"] and second not in state["candidates"]
    assert proposal_for(state, action["request_proposal_id"])["status"] == "import_rejected"
    assert state["used"]["proposals"] == run.status()["search"]["reuse_proposals"] == 2
    assert selection(state) == before
    assert_unmeasured(state)


def test_invalid_history_requests_are_charged_before_verification(tmp_path):
    run = create(tmp_path / "current", search_policy={"reuse_proposal_limit": 1})
    with pytest.raises(run_module.RunError):
        run.warm_start(tmp_path / "missing")
    state = run.status()["state"]
    assert state["used"]["proposals"] == run.status()["search"]["reuse_proposals"] == 1
    assert state["imports"][0]["status"] == "rejected"
    assert state["imports"][0]["registered"] == []
    assert state["proposals"][0]["status"] == "import_rejected"
    assert_error("reuse_proposal_budget_exhausted", lambda: run.warm_start(tmp_path / "missing"))
    assert len(run.status()["state"]["imports"]) == 1
    assert_unmeasured(state)


def test_interrupted_import_records_partial_steps_and_does_not_auto_resume(tmp_path, history_chain, monkeypatch):
    history, first, _ = history_chain
    run = create(tmp_path / "current")
    original_prepare = run._prepare
    calls = []

    def interrupt_second(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(run, "_prepare", interrupt_second)
    before = selection(run.status()["state"])
    with pytest.raises(KeyboardInterrupt):
        run.warm_start(history.directory)
    state = run.status()["state"]
    action = state["imports"][0]
    assert action["status"] == "interrupted"
    assert [step["candidate_id"] for step in action["registered"]] == [first]
    assert proposal_for(state, action["request_proposal_id"])["status"] == "import_interrupted"
    run.resume()
    after = run.status()["state"]
    assert after["imports"] == state["imports"]
    assert after["used"] == state["used"]
    assert len(calls) == 2
    assert selection(after) == before
    assert_unmeasured(after)


def test_resume_marks_abandoned_import_and_request_without_restarting(tmp_path):
    run = create(tmp_path / "current")

    def abandoned(state):
        state["imports"] = [{"id": "lost", "status": "running", "registered": []}]
        state["proposals"].append({"id": "request", "status": "import_requested", "reuse": True})
        state["used"]["proposals"] += 1

    mutate_state(run, abandoned)
    run.resume()
    state = run.status()["state"]
    assert state["imports"][0]["status"] == "interrupted"
    assert state["proposals"][0]["status"] == "import_interrupted"
    assert state["used"]["proposals"] == 1
    assert_unmeasured(state)


@pytest.mark.parametrize("crash_at", ["request", "first_step"])
def test_hard_exit_requires_resume_before_external_operations(tmp_path, history_chain, crash_at):
    history, first, _ = history_chain
    run = create(tmp_path / "current")
    child = os.fork()
    if child == 0:
        original_save = run._save

        def crash_after_save(state):
            original_save(state)
            has_request = any(p["status"] == "import_requested" for p in state["proposals"])
            has_step = any(action["registered"] for action in state.get("imports", []))
            if (crash_at == "request" and has_request) or (crash_at == "first_step" and has_step):
                os._exit(73)

        run._save = crash_after_save
        try:
            run.warm_start(history.directory)
        except BaseException:
            os._exit(74)
        os._exit(75)
    _, status = os.waitpid(child, 0)
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 73
    before = run.status()["state"]
    fake = FakeEvaluator()
    assert_error("recovery_required", run.observe)
    assert_error("recovery_required", lambda: run.evaluate("original", fake))
    assert_error("recovery_required", lambda: run.warm_start(history.directory))
    assert not fake.calls
    with pytest.raises(HistoryError, match="unfinished"):
        load_history(run.directory, run.status()["manifest"])
    run.resume()
    after = run.status()["state"]
    assert after["used"] == before["used"]
    assert after["used"]["proposals"] == (1 if crash_at == "request" else 2)
    assert (first in after["candidates"]) == (crash_at == "first_step")
    assert after["proposals"][0]["status"] == "import_interrupted"
    assert all(action["status"] == "interrupted" for action in after.get("imports", []))
    assert_unmeasured(after)
    assert run.observe()["parent_id"] == "original"
    run.evaluate("original", fake)
    assert len(fake.calls) == 1


@pytest.mark.parametrize("reject_static", [False, True])
def test_normalized_root_uses_current_archive_and_charged_step(tmp_path, reject_static):
    source = _SYNTH.replace("  s_endpgm", "  s_waitcnt vmcnt(0)\n  s_endpgm")
    history = create(tmp_path / "history", source)
    assert history.source("normalized") != source
    history.evaluate("original", FakeEvaluator())
    history.evaluate("normalized", FakeEvaluator())
    history.confirm("normalized", evaluator())
    run = create(tmp_path / "current", source)
    if reject_static:
        mutate_state(run, lambda state: state["candidates"]["normalized"].update(static_ok=False))
        assert_error("history_mismatch", lambda: run.warm_start(history.directory))
        state = run.status()["state"]
        assert state["used"]["proposals"] == 1
        assert state["imports"][0]["registered"] == []
    else:
        action = run.warm_start(history.directory)
        state = run.status()["state"]
        assert action["candidate_id"] == "normalized"
        assert action["recipe"][0]["spec"]["kind"] == "ladder"
        assert state["candidates"]["normalized"]["reuse"]
        assert state["used"]["proposals"] == run.status()["search"]["reuse_proposals"] == 2
        assert len(state["candidates"]) == 2
    assert_unmeasured(state)
    assert state["exploration_parent_id"] == "original"


def test_duplicate_import_still_costs_requests_and_steps(tmp_path, history_chain):
    history, _, _ = history_chain
    run = create(tmp_path / "current")
    first = run.warm_start(history.directory)
    initial_candidates = copy.deepcopy(run.status()["state"]["candidates"])
    second = run.warm_start(history.directory)
    state = run.status()["state"]
    assert first["candidate_id"] == second["candidate_id"]
    assert all(step["status"] == "duplicate" for step in second["registered"])
    assert state["used"]["proposals"] == run.status()["search"]["reuse_proposals"] == 6
    assert state["candidates"] == initial_candidates
    assert_unmeasured(state)
