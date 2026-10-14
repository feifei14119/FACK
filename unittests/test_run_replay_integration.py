"""Controller replay uses durable budgets, ordinary prepare, and no client calls."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from agent import replay_controller
from agent.run import RunController, RunError
from unittests.test_session import _SYNTH, _loads
from unittests.test_tuning_run import CONTRACT, FakeEvaluator


def siblings(tmp_path, *, conflict=False, reuse=False, search_policy=None, proposal_limit=64):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=1,
                               protect_prefetch=False, proposal_limit=proposal_limit,
                               search_policy=search_policy)
    run.evaluate("original", FakeEvaluator())
    ids = []
    for slot, load in ((0, 0), (1, 0 if conflict else 1)):
        obs = run.observe()
        proposal = run.prepare(obs["observation_id"], obs["base_sha256"],
                               {"kind": "layout", "layout": {str(slot): [_loads(_SYNTH)[1][load]]}},
                               hypothesis={"source": "history"} if reuse and slot == 1 else None)
        ids.append(proposal["candidate_id"])
        run.evaluate(ids[-1], FakeEvaluator())
    run.select_parent(ids[0])
    return run, ids[0], ids[1]


def rewrite_state(run, mutate):
    path = run.directory / "state.json"
    state = json.loads(path.read_text())
    mutate(state)
    path.write_text(json.dumps(state))


@pytest.mark.parametrize("method", ["replay", "combine"])
def test_sibling_replay_prepares_combination_with_provenance_without_promotion(tmp_path, method):
    run, target, source = siblings(tmp_path)
    before = run.status()["state"]
    prepared = getattr(run, method)(source)
    after = run.status()["state"]
    assert prepared["status"] == "prepared"
    assert after["used"]["proposals"] == before["used"]["proposals"] + 2
    assert after["used"]["eval_calls"] == before["used"]["eval_calls"]
    assert after["exploration_parent_id"] == target and after["incumbent_id"] is None
    assert after["candidates"][prepared["candidate_id"]]["parent_id"] == target
    provenance = prepared["provenance"]
    assert provenance["mode"] == "replay" and provenance["source_candidate_id"] == source
    assert provenance["source_chain"] and provenance["target_chain"] and provenance["mapping"]
    assert prepared["diagnostics"]["ok_vs_original"] is True
    request = next(p for p in after["proposals"] if p["id"] == provenance["request_id"])
    assert request["status"] == "replay_completed"
    assert request["materialized_proposal_id"] == prepared["id"]
    assert not hasattr(run, "_active_replay_request_id")


def test_conflicting_replay_is_charged_and_preserves_parent(tmp_path):
    run, target, source = siblings(tmp_path, conflict=True)
    before = run.status()["state"]
    with pytest.raises(RunError) as exc:
        run.replay(source)
    assert exc.value.code == "intent_conflict"
    after = run.status()["state"]
    assert after["used"]["proposals"] == before["used"]["proposals"] + 1
    assert after["used"]["eval_calls"] == before["used"]["eval_calls"]
    assert after["exploration_parent_id"] == target and after["incumbent_id"] is None
    assert after["proposals"][-1]["status"] == "replay_rejected"
    assert after["proposals"][-1]["provenance"]["source_candidate_id"] == source
    run.observe()  # normal rejection does not leave the run pending


def test_replay_requires_latest_successful_source_screen(tmp_path):
    run, target, source = siblings(tmp_path)
    rewrite_state(run, lambda state: [batch.update(status="incorrect") for batch in state["batches"].values()
                                      if batch["candidate_id"] == source])
    with pytest.raises(RunError) as exc:
        run.replay(source)
    assert exc.value.code == "screen_required"
    state = run.status()["state"]
    assert state["used"]["proposals"] == 3
    assert state["exploration_parent_id"] == target


@pytest.mark.parametrize("tamper", ["observation", "recipe", "artifact"])
def test_stale_or_tampered_source_chain_is_rejected_with_charged_record(tmp_path, tamper):
    run, target, source = siblings(tmp_path)
    if tamper == "artifact":
        state = run.status()["state"]
        path = run.directory / state["candidates"][source]["artifact"]["path"]
        path.write_text(path.read_text() + "// changed archive\n")
    else:
        def mutate(state):
            proposal = next(p for p in state["proposals"] if p.get("candidate_id") == source)
            if tamper == "observation":
                del state["observations"][proposal["observation_id"]]
            else:
                wrong = {"2": list(state["candidates"][source]["spec"]["layout"].values())[0]}
                proposal["spec"]["layout"] = wrong
                state["candidates"][source]["spec"]["layout"] = wrong
        rewrite_state(run, mutate)
    with pytest.raises(RunError) as exc:
        run.replay(source)
    assert exc.value.code in ("invalid_history", "artifact_mismatch", "artifact_invalid")
    after = run.status()["state"]
    assert after["used"]["proposals"] == 3
    assert after["exploration_parent_id"] == target
    assert after["proposals"][-1]["status"] == "replay_rejected"


def test_source_reuse_cannot_be_relabelled_independent_on_clean_target(tmp_path):
    run, _, source = siblings(tmp_path, reuse=True)
    before = run.status()["search"]["reuse_proposals"]
    proposal = run.replay(source)
    status = run.status()
    assert proposal["reuse"] and proposal["hypothesis"]["source"] == "history"
    assert status["state"]["candidates"][proposal["candidate_id"]]["reuse"] is True
    assert status["search"]["reuse_proposals"] == before + 2


def test_failed_reuse_mapping_still_consumes_reuse_allowance(tmp_path):
    run, _, source = siblings(tmp_path, conflict=True, reuse=True)
    before = run.status()["search"]["reuse_proposals"]
    with pytest.raises(RunError, match="retain"):
        run.replay(source)
    after = run.status()
    assert after["search"]["reuse_proposals"] == before + 1
    assert after["state"]["proposals"][-1]["reuse_charged"] is True


def test_replay_materialization_honors_remaining_reuse_budget(tmp_path):
    run, target, source = siblings(tmp_path, reuse=True, search_policy={"reuse_proposal_limit": 2})
    with pytest.raises(RunError) as exc:
        run.replay(source)
    assert exc.value.code == "reuse_proposal_budget_exhausted"
    state = run.status()["state"]
    assert state["used"]["proposals"] == 3 and state["exploration_parent_id"] == target
    # Only the initial replay request was charged; _prepare could not start.
    assert run.status()["search"]["reuse_proposals"] == 2


def test_replay_cannot_materialize_or_retry_after_exhausting_global_proposals(tmp_path):
    run, target, source = siblings(tmp_path, proposal_limit=3)
    for _ in range(2):
        with pytest.raises(RunError) as exc:
            run.replay(source)
        assert exc.value.code == "proposal_budget_exhausted"
    state = run.status()["state"]
    assert state["used"]["proposals"] == len(state["proposals"]) == 3
    assert state["exploration_parent_id"] == target
    assert state["proposals"][-1]["status"] == "replay_rejected"


def test_unknown_replay_source_is_not_an_unlimited_free_request(tmp_path):
    run, target, _ = siblings(tmp_path)
    with pytest.raises(RunError) as exc:
        run.replay("missing-source")
    assert exc.value.code == "unknown_candidate"
    state = run.status()["state"]
    assert state["used"]["proposals"] == 3 and state["exploration_parent_id"] == target
    assert state["proposals"][-1]["provenance"]["source_candidate_id"] == "missing-source"


def test_hard_exit_after_mapping_blocks_external_work_until_explicit_resume(tmp_path):
    run, target, source = siblings(tmp_path)
    code = """
import os, sys
from agent.run import RunController
run = RunController(sys.argv[1])
def exit_before_observation(*args, **kwargs):
    os._exit(9)
run._observe = exit_before_observation
run.replay(sys.argv[2])
"""
    result = subprocess.run([sys.executable, "-c", code, str(run.directory), source],
                            cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
    assert result.returncode == 9, result.stderr
    restarted = RunController(run.directory)
    state = restarted.status()["state"]
    assert state["used"]["proposals"] == 3
    assert state["proposals"][-1]["status"] == "replay_requested"
    assert state["proposals"][-1]["planning_status"] == "ready"
    with pytest.raises(RunError) as exc:
        restarted.observe()
    assert exc.value.code == "recovery_required"
    restarted.resume()
    state = restarted.status()["state"]
    assert state["proposals"][-1]["status"] == "replay_interrupted"
    assert state["used"]["proposals"] == 3 and state["exploration_parent_id"] == target
    restarted.observe()


def test_keyboard_interrupt_is_charged_and_clears_private_token(tmp_path, monkeypatch):
    run, target, source = siblings(tmp_path)
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(replay_controller, "replay_intent", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run.replay(source)
    state = run.status()["state"]
    assert state["used"]["proposals"] == 3
    assert state["proposals"][-1]["status"] == "replay_interrupted"
    assert state["exploration_parent_id"] == target and state["incumbent_id"] is None
    assert not hasattr(run, "_active_replay_request_id")
