import copy

import pytest

from agent import run as run_module
from agent import knowledge
from unittests.test_tuning_run import run, prepare, FakeEvaluator, assert_error


def test_ledger_binds_intent_and_retains_duplicate_and_raw_results(run):
    obs = run.observe()
    first = prepare(run, obs)
    second = prepare(run, obs)
    assert first["intent_id"] == second["intent_id"]
    assert first["id"] != second["id"]
    assert first["diagnostics"]["actual_changes"]["bytes_changed"]
    assert first["diagnostics"]["allowance_source_sha256"] == obs["base_sha256"]
    run.evaluate("original", FakeEvaluator())
    batch = run.evaluate(first["candidate_id"], FakeEvaluator())
    rows = run.ledger()["rows"]
    assert [r["status"] for r in rows] == ["prepared", "duplicate"]
    assert rows[0]["batches"][0]["id"] == batch["id"]
    assert rows[0]["comparisons"] == []


def test_explanation_references_validated_and_cannot_change_verdict(run):
    obs = run.observe()
    spec = {"kind": "order", "order": [8, 7]}
    meta = {"hypothesis": "reduce exposed load latency", "expected_observable": "less VMEM stall",
            "direction": "load_early", "source": "observation",
            "evidence_refs": [{"kind": "observation", "id": obs["observation_id"]}]}
    proposal = run.prepare(obs["observation_id"], obs["base_sha256"], spec, hypothesis=meta)
    before = run.status()["state"]
    run.annotate("candidate may help; still unmeasured", [{"kind": "proposal", "id": proposal["id"]}])
    after = run.status()["state"]
    assert before["batches"] == after["batches"]
    assert before["confirmation_status"] == after["confirmation_status"]
    assert run.ledger()["annotations"][0]["authority"] == "agent_interpretation_only"
    with pytest.raises(ValueError, match="does not exist"):
        run.annotate("invented evidence", [{"kind": "batch", "id": "missing"}])
    bad = dict(meta, verdict="confirmed_gain")
    assert_error("prepare_failed", lambda: run.prepare(obs["observation_id"], obs["base_sha256"], spec, hypothesis=bad))
    assert run.ledger()["rows"][-1]["status"] == "rejected"


def test_fixed_original_gate_can_reject_driver_success(run, monkeypatch):
    real = run_module.diagnose_candidate
    def new_warning(*args, **kwargs):
        result = real(*args, **kwargs)
        result["ok_vs_original"] = False
        result["new_findings"] = [{"id": "introduced", "message": "new hazard"}]
        return result
    monkeypatch.setattr(run_module, "diagnose_candidate", new_warning)
    assert_error("verify_failed", lambda: prepare(run))
    state = run.status()["state"]
    assert len(state["candidates"]) == 2
    assert state["proposals"][-1]["diagnostics"]["new_findings"][0]["id"] == "introduced"


def test_specific_orders_no_longer_share_global_transform_id(tmp_path):
    a = {"kind": "order", "order": [8, 7]}
    b = {"kind": "order", "order": [7, 8]}
    assert knowledge._transform_id(a) != knowledge._transform_id(b)
    for spec in (a, b):
        knowledge.log_experiment({"transform": spec, "correct": False, "verdict": "incorrect"}, str(tmp_path))
    assert knowledge.induce_skills(str(tmp_path)) == []
