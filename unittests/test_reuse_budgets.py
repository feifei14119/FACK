"""Historical/knowledge guidance cannot consume unlimited current-run search."""
from agent.run import RunController
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, assert_error
from unittests.test_session import _SYNTH, _loads
from unittests.test_paired_validation import POLICY, evaluator


def make(tmp_path, policy, paired=False):
    return RunController.create(tmp_path / "run", _SYNTH, CONTRACT, protect_prefetch=False,
                                perf_repeats=1, eval_call_limit=100,
                                final_eval_reserve=16 if paired else 0,
                                comparison_policy=POLICY if paired else None, search_policy=policy)


def prepare(run, index=0, source="knowledge"):
    obs = run.observe()
    spec = {"kind": "layout", "layout": {"0": [_loads(_SYNTH)[1][index]]}}
    return run.prepare(obs["observation_id"], obs["base_sha256"], spec,
                       hypothesis={"source": source, "direction": "same_direction"})


def test_reuse_proposal_and_evaluation_caps_cannot_be_relabelled(tmp_path):
    run = make(tmp_path, {"reuse_proposal_limit": 1, "reuse_eval_call_limit": 1})
    candidate = prepare(run)["candidate_id"]
    assert_error("reuse_proposal_budget_exhausted", lambda: prepare(run, source="observation"))
    state = run.status()["state"]
    assert state["candidates"][candidate]["reuse"] is True
    assert state["proposals"][-1]["status"] == "rejected"
    assert state["proposals"][-1]["reuse"] is True
    assert state["proposals"][-1]["reuse_charged"] is False
    assert run.status()["search"]["reuse_proposals"] == 1
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    assert_error("reuse_budget_exhausted", lambda: run.evaluate(candidate, FakeEvaluator(), repeat=True))
    assert run.status()["search"]["reuse_eval_calls"] == 1


def test_descendant_of_historical_candidate_inherits_reuse(tmp_path):
    run = make(tmp_path, {"reuse_proposal_limit": 2})
    parent = prepare(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(parent, FakeEvaluator())
    run.select_parent(parent)
    suggestion = run.suggest(n=4)
    assert suggestion["suggestions"]
    choice = suggestion["suggestions"][0]
    obs = suggestion["observation"]
    proposal = run.prepare(obs["observation_id"], obs["base_sha256"], choice["spec"],
                           hypothesis=choice["hypothesis"])
    assert proposal["hypothesis"]["source"] == "observation"
    assert proposal["reuse"] is True
    assert run.status()["state"]["candidates"][proposal["candidate_id"]]["reuse"] is True
    assert_error("reuse_proposal_budget_exhausted", lambda: run.prepare(
        obs["observation_id"], obs["base_sha256"], choice["spec"], hypothesis=choice["hypothesis"]))


def test_confirmation_prechecks_complete_reuse_cost_without_spending(tmp_path):
    run = make(tmp_path, {"reuse_eval_call_limit": 1}, paired=True)
    candidate = prepare(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    fake = evaluator()
    assert_error("reuse_budget_exhausted", lambda: run.confirm(candidate, fake))
    assert not fake.calls
    assert run.status()["state"]["comparisons"] == {}


def test_final_reserve_remains_available_after_reuse_allowance_exhausted(tmp_path):
    run = make(tmp_path, {"reuse_eval_call_limit": 1 + POLICY["confirm_pairs"]}, paired=True)
    candidate = prepare(run)["candidate_id"]
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    assert run.confirm(candidate, evaluator())["verdict"] == "confirmed_gain"
    assert run.finalize(evaluator())["status"] == "final_recommended"
