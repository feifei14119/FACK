"""Public reuse commands preserve client indirection and current selection."""
import json

from unittests.test_tuning_run import cli
from unittests.test_session import _SYNTH, _loads


def test_cli_replay_rebuilds_without_calling_client_or_selecting_parent(cli, tmp_path):
    invoke, seed, cl, fake, _ = cli
    directory = invoke("init", str(seed), "--client", cl.spec, "--perf-repeats", "1",
                       "--no-protect-prefetch")["run_dir"]
    obs = invoke("observe", directory)
    def prepared(slot, index):
        path = tmp_path / ("layout-{}-{}.json".format(slot, index))
        path.write_text(json.dumps({"kind": "layout", "layout": {str(slot): [_loads(_SYNTH)[1][index]]}}))
        return invoke("prepare", directory, "--observation", obs["observation_id"],
                      "--base-sha256", obs["base_sha256"], "--spec-file", str(path))["candidate_id"]
    source, target = prepared(1, 1), prepared(0, 0)
    for candidate in ("original", source, target):
        invoke("eval", directory, candidate)
    invoke("select-parent", directory, target)
    count = len(fake.calls)
    result = invoke("combine", directory, source)
    assert result["candidate_id"] not in (source, target)
    assert result["provenance"]["source_candidate_id"] == source
    status = invoke("status", directory)
    assert status["state"]["exploration_parent_id"] == target
    assert status["state"]["incumbent_id"] is None
    assert status["state"]["used"]["proposals"] == 4
    assert len(fake.calls) == count


def test_cli_history_import_requires_fresh_current_screening(cli, tmp_path):
    from agent.run import RunController
    from unittests.test_tuning_run import FakeEvaluator, prepare
    from unittests.test_paired_validation import POLICY, evaluator
    invoke, seed, cl, fake, _ = cli
    policy_path = tmp_path / "comparison.json"
    policy_path.write_text(json.dumps(POLICY))
    def init(name):
        return invoke("init", str(seed), "--client", cl.spec, "--run-id", name,
                      "--perf-repeats", "1", "--no-protect-prefetch", "--eval-calls", "100",
                      "--final-reserve", "16", "--comparison-policy", str(policy_path))["run_dir"]
    history_dir = init("history")
    history = RunController(history_dir)
    source = prepare(history)["candidate_id"]
    history.evaluate("original", FakeEvaluator())
    history.evaluate(source, FakeEvaluator())
    history.confirm(source, evaluator())
    current = init("current")
    recipe = invoke("history", current, history_dir, "--candidate", source)
    assert recipe["requires_evaluation"] is True
    imported = invoke("warm-start", current, history_dir)
    candidate = imported["candidate_id"]
    status = invoke("status", current)
    assert status["state"]["used"] == {"eval_calls": 0, "proposals": 2}
    assert status["state"]["incumbent_id"] is None
    assert status["state"]["exploration_parent_id"] == "original"
    assert not cl.make_evaluator.called
    assert invoke("eval", current, candidate, expected=2)["error"]["code"] == "baseline_required"
    invoke("eval", current, "original")
    invoke("eval", current, candidate)
    assert len(fake.calls) == 2
    ledger = invoke("ledger", current)
    assert ledger["imports"][0]["source_evidence_ref"]["candidate_id"] == source
    assert ledger["final_result"] is None
