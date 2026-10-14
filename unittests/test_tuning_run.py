"""Persistent run contracts using real reorder fixtures and CPU-only evaluators."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent import run as run_module
from agent.run import RunController, RunError
from harness.evaluator import EvalResult
from tools import tune_run
from unittests.test_session import _SYNTH, _loads


CONTRACT = {"client": "fake", "params": ["x=1", "x=2", "--check", "a b"]}


class FakeEvaluator:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def evaluate(self, path, with_counters=False):
        assert with_counters is False
        self.calls.append(Path(path).read_bytes())
        result = self.results.pop(0) if self.results else passed()
        if isinstance(result, BaseException):
            raise result
        return result


def passed(score=100):
    return EvalResult(compiled=True, correct=True, tflops=score,
                      detail={"raw": "fake client output"})


@pytest.fixture
def run(tmp_path):
    return RunController.create(tmp_path / "run", _SYNTH, CONTRACT,
                                perf_repeats=2, protect_prefetch=False)


def prepare(run, observation=None, spec=None):
    obs = observation or run.observe()
    spec = spec if spec is not None else {
        "kind": "layout", "layout": {"0": [_loads(_SYNTH)[1][0]]}}
    return run.prepare(obs["observation_id"], obs["base_sha256"], spec)


def assert_error(code, fn):
    with pytest.raises(RunError) as exc:
        fn()
    assert exc.value.code == code


def test_init_archives_exact_bytes_and_observation(tmp_path):
    src = _SYNTH.replace("\n", "\r\n")
    run = RunController.create(tmp_path / "run", src, CONTRACT)
    obs = run.observe()
    other = RunController(run.directory)
    state = other.status()["state"]
    assert other.source("original").encode() == src.encode()
    assert state["observations"][obs["observation_id"]] == obs
    assert state["used"] == {"eval_calls": 0, "proposals": 0}
    assert state["confirmation_status"] == "not_performed"
    assert state["incumbent_id"] is None
    assert set(state["candidates"]) == {"original", "normalized"}
    with pytest.raises(FileExistsError):
        RunController.create(run.directory, src, CONTRACT)


def test_prepare_persists_candidate_and_deduplicates(run):
    obs = run.observe()
    first = prepare(run, obs)
    assert first["status"] == "prepared"
    second = prepare(RunController(run.directory), obs)
    assert second["status"] == "duplicate"
    assert first["candidate_id"] == second["candidate_id"]
    state = run.status()["state"]
    assert state["used"] == {"eval_calls": 0, "proposals": 2}
    assert state["candidates"][first["candidate_id"]]["parent_id"] == "original"
    assert run.source(first["candidate_id"]) != _SYNTH


@pytest.mark.parametrize("spec", [
    {"kind": "layout", "layout": {"0": [True]}},
    {"kind": "layout", "layout": {"0": [7.9]}},
    {"kind": "layout", "layout": {"0": ["7"]}},
    {"kind": "layout", "layout": {"00": [7]}},
    {"kind": "layout", "layout": {"-1": [7]}},
    {"kind": "layout", "layout": {"0": [7], "1": [7]}},
    {"kind": "layout", "layout": {"0": "7"}},
    {"kind": "layout", "layout": {}, "opt_level": 3},
    {"kind": "layout", "layout": {}, "region": "epilogue"},
    {"kind": "order", "order": [False]},
    {"kind": "order", "order": [7, 7]},
    {"kind": "order"},
    {"kind": "ladder", "level": 3},
    [],
])
def test_malformed_proposals_are_recorded_and_charged(run, spec):
    assert_error("invalid_spec", lambda: prepare(run, spec=spec))
    state = run.status()["state"]
    assert state["used"] == {"eval_calls": 0, "proposals": 1}
    assert state["proposals"][-1]["error_code"] == "invalid_spec"


def test_partial_placement_is_rejected(run):
    spec = {"kind": "layout", "layout": {"0": [7], "99": [8]}}
    assert_error("proposal_rejected", lambda: prepare(run, spec=spec))
    state = run.status()["state"]
    assert len(state["candidates"]) == 2
    assert state["proposals"][-1]["report"]["skipped"]


def test_order_intent_reuses_engine_and_checks_ids(run):
    proposal = prepare(run, spec={"kind": "order", "order": [8, 7]})
    text = run.source(proposal["candidate_id"])
    assert text.index("v[8:11]") < text.index("v[4:7]")
    assert_error("proposal_rejected", lambda: prepare(run, spec={
        "kind": "order", "order": [9999]}))


def test_proposal_limit_is_persistent(tmp_path):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT, proposal_limit=1)
    prepare(run)
    assert_error("proposal_budget_exhausted", lambda: prepare(RunController(run.directory)))
    assert run.status()["state"]["used"]["proposals"] == 1


def test_original_gate_contract_cache_and_explicit_repeat(run):
    fake = FakeEvaluator(passed(80), passed(100))
    assert_error("baseline_required", lambda: run.evaluate("normalized", fake))
    assert_error("contract_mismatch", lambda: run.evaluate("original", fake,
                 evaluation_contract={"params": list(reversed(CONTRACT["params"]))}))
    assert not fake.calls
    result = run.evaluate("original", fake, evaluation_contract=CONTRACT)
    assert result["measurement"]["tflops"] == 90
    other = RunController(run.directory)
    assert other.evaluate("original", fake)["cached"] is True
    assert len(fake.calls) == 2
    assert other.evaluate("original", fake, repeat=True)["cached"] is False
    assert len(fake.calls) == 4
    assert other.status()["state"]["used"]["eval_calls"] == 4


@pytest.mark.parametrize("result,status", [
    (EvalResult(compiled=False), "compile_failed"),
    (EvalResult(compiled=True, correct=False), "incorrect"),
    (EvalResult(compiled=True, tflops=100), "measurement_invalid"),
    (passed(float("nan")), "measurement_invalid"),
    (RuntimeError("client unavailable"), "measurement_invalid"),
])
def test_baseline_failures_stop_candidates_and_do_not_retry(run, result, status):
    fake = FakeEvaluator(result)
    batch = run.evaluate("original", fake)
    assert batch["status"] == status
    assert run.evaluate("original", fake)["cached"] is True
    assert_error("baseline_required", lambda: run.evaluate("normalized", fake))
    assert len(fake.calls) == 1
    assert run.status()["state"]["used"]["eval_calls"] == 1


def test_hard_budget_and_final_reserve(tmp_path):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT,
                                eval_call_limit=5, final_eval_reserve=2, perf_repeats=2)
    fake = FakeEvaluator()
    run.evaluate("original", fake)
    assert_error("eval_budget_exhausted", lambda: run.evaluate("normalized", fake))
    assert_error("eval_budget_exhausted", lambda: run.evaluate("original", fake, repeat=True))
    assert len(fake.calls) == 2
    assert run.status()["state"]["used"]["eval_calls"] == 2


def test_parent_selection_invalidates_old_observations_without_promotion(run):
    obs = run.observe()
    proposal = prepare(run, obs)
    candidate = proposal["candidate_id"]
    assert_error("unmeasured_parent", lambda: run.select_parent(candidate))
    run.evaluate("original", FakeEvaluator())
    run.evaluate(candidate, FakeEvaluator())
    selection = run.select_parent(candidate)
    assert selection["incumbent_id"] is None
    assert_error("stale_observation", lambda: prepare(run, obs))
    fresh = RunController(run.directory).observe()
    assert fresh["parent_id"] == candidate
    assert fresh["base_sha256"] != obs["base_sha256"]
    assert fresh["parent_revision"] == obs["parent_revision"] + 1
    no_change = prepare(run, fresh, {"kind": "layout", "layout": {}})
    assert no_change["status"] == "no_change"
    assert no_change["candidate_id"] == candidate


def test_interrupted_call_is_charged_and_requires_explicit_recovery(run):
    fake = FakeEvaluator(passed(88), KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        run.evaluate("original", fake)
    state = RunController(run.directory).status()["state"]
    attempts = list(state["attempts"].values())
    returned = [a for a in attempts if a["status"] == "returned"]
    assert returned[0]["result"]["tflops"] == 88
    assert sum(a["status"] == "running" for a in attempts) == 1
    assert state["used"]["eval_calls"] == 2
    assert_error("recovery_required", run.observe)
    recovered = run.resume()
    assert len(recovered["recovered_attempt_ids"]) == 1
    assert recovered["used"]["eval_calls"] == 2
    assert_error("repeat_required", lambda: run.evaluate("original", fake))
    run.evaluate("original", fake, repeat=True)
    assert run.status()["state"]["used"]["eval_calls"] == 4


def test_process_exit_preserves_returned_sample_and_inflight_charge(run):
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
        return EvalResult(compiled=True, correct=True, tflops=91)
RunController(sys.argv[1]).evaluate('original', Dies())
"""
    result = subprocess.run([sys.executable, "-c", code, str(run.directory)],
                            cwd=str(run_module.REPO), capture_output=True, text=True)
    assert result.returncode == 9, result.stderr
    state = run.status()["state"]
    assert state["used"]["eval_calls"] == 2
    assert any(a["result"] and a["result"]["tflops"] == 91
               for a in state["attempts"].values())
    assert len(run.resume()["recovered_attempt_ids"]) == 1


def test_interrupted_preparation_needs_recovery(run, monkeypatch):
    obs = run.observe()
    with monkeypatch.context() as m:
        m.setattr(run_module.driver, "build_candidate", Mock(side_effect=KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            prepare(run, obs)
    assert_error("recovery_required", run.observe)
    run.resume()
    state = run.status()["state"]
    assert state["used"]["proposals"] == 1
    assert state["proposals"][-1]["status"] == "interrupted"
    assert prepare(run, obs)["status"] == "prepared"


def test_deadline_stops_new_calls_without_interrupting_client(tmp_path, monkeypatch):
    run = RunController.create(tmp_path / "run", _SYNTH, CONTRACT,
                                perf_repeats=2, wall_time_limit=60)
    created = run.status()["manifest"]["created_at"]
    now = [created + 1]
    monkeypatch.setattr(run_module.time, "time", lambda: now[0])

    class Slow:
        def evaluate(self, path, with_counters=False):
            now[0] = created + 61
            return passed()

    batch = run.evaluate("original", Slow())
    assert batch["status"] == "measurement_invalid"
    assert "deadline" in batch["measurement"]["error"]
    assert run.status()["state"]["used"]["eval_calls"] == 1
    assert_error("wall_time_exhausted", lambda: run.evaluate("original", Slow(), repeat=True))
    assert_error("wall_time_exhausted", lambda: prepare(run))


def test_manifest_artifact_and_engine_changes_fail_closed(run, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(run_module, "engine_identity", lambda: "changed")
        assert run.status()["environment_matches"] is False
        assert_error("environment_changed", run.observe)
        assert_error("environment_changed", run.resume)
    archive = run.status()["state"]["candidates"]["original"]["artifact"]["path"]
    (run.directory / archive).write_text("corrupted")
    assert_error("artifact_invalid", run.resume)
    assert_error("artifact_invalid", lambda: run.evaluate("original", FakeEvaluator()))
    path = run.directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["budget"]["eval_call_limit"] += 100
    path.write_text(json.dumps(manifest))
    assert_error("manifest_mismatch", run.status)


def test_working_source_mutation_invalidates_batch_not_archive(run):
    class Mutates:
        def evaluate(self, path, with_counters=False):
            Path(path).write_text("changed by client")
            return passed()

    batch = run.evaluate("original", Mutates())
    assert batch["status"] == "measurement_invalid"
    assert run.source("original") == _SYNTH
    assert run.status()["state"]["used"]["eval_calls"] == 1


def test_second_process_cannot_acquire_active_run_lock(run):
    with (run.directory / ".lock").open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([sys.executable, "tools/tune_run.py", "status", str(run.directory)],
                                cwd=str(run_module.REPO), capture_output=True, text=True)
        assert result.returncode == 2, result.stderr
        assert json.loads(result.stdout)["error"]["code"] == "run_busy"


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):
    adapter = tmp_path / "client.py"
    adapter.write_text("# Fake client implementation identity\n")
    fake = FakeEvaluator()
    cl = SimpleNamespace(spec="fake/case", module=SimpleNamespace(__file__=str(adapter)),
                         out_dir=str(tmp_path / "tune_out"),
                         make_evaluator=Mock(return_value=fake))
    monkeypatch.setattr(tune_run.clients, "resolve", lambda spec: cl)
    monkeypatch.setattr(tune_run, "EVAL_LOCK", tmp_path / "eval.lock")

    def invoke(*argv, expected=0):
        rc = tune_run.main(list(argv))
        out = capsys.readouterr()
        assert rc == expected, out
        return json.loads(out.out)

    seed = tmp_path / "seed.s"
    seed.write_bytes(_SYNTH.replace("\n", "\r\n").encode())
    return invoke, seed, cl, fake, adapter


def test_cli_cpu_flow_frozen_params_and_lazy_client(cli, tmp_path):
    invoke, seed, cl, fake, _ = cli
    params = ["key=1", "key=2", "--check", "a b"]
    initialized = invoke("init", str(seed), "--client", "fake/case", "--run-id", "test",
                         "--perf-repeats", "1", "--loop", "9", "--", *params)
    directory = initialized["run_dir"]
    assert Path(directory) == Path(cl.out_dir) / "runs/test"
    assert initialized["manifest"]["evaluation_contract"]["params"] == params
    obs = invoke("observe", directory)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"kind": "layout", "layout": {"0": [7]}}))
    candidate = invoke("prepare", directory, "--observation", obs["observation_id"],
                       "--base-sha256", obs["base_sha256"], "--spec-file", str(spec))["candidate_id"]
    assert not cl.make_evaluator.called
    assert invoke("eval", directory, candidate, expected=2)["error"]["code"] == "baseline_required"
    assert not cl.make_evaluator.called
    invoke("eval", directory, "original")
    assert cl.make_evaluator.call_args.kwargs["params"] == params
    assert cl.make_evaluator.call_args.kwargs["loop"] == 9
    assert cl.make_evaluator.call_args.kwargs["seed_src"].encode() == seed.read_bytes()
    assert invoke("eval", directory, "original")["cached"] is True
    assert cl.make_evaluator.call_count == 1
    invoke("eval", directory, candidate)
    invoke("select-parent", directory, candidate)
    assert invoke("status", directory)["state"]["exploration_parent_id"] == candidate
    assert invoke("resume", directory)["used"]["eval_calls"] == 2
    assert len(fake.calls) == 2
    assert invoke("eval", directory, "original", "--", "key=3", expected=2)["error"]["code"] == "arguments"


def test_cli_changed_client_and_shared_lock_reject_without_calls(cli):
    invoke, seed, cl, fake, adapter = cli
    directory = invoke("init", str(seed), "--client", "fake/case")["run_dir"]
    with tune_run.evaluation_lock():
        result = invoke("eval", directory, "original", expected=2)
        assert result["error"]["code"] == "evaluation_busy"
    adapter.write_text("# modified client\n")
    result = invoke("eval", directory, "original", expected=2)
    assert result["error"]["code"] == "contract_mismatch"
    assert not cl.make_evaluator.called
    assert not fake.calls
    assert invoke("status", directory)["state"]["used"]["eval_calls"] == 0


def test_cli_rejects_path_escape_and_bad_arguments(cli):
    invoke, seed, cl, _, _ = cli
    assert invoke("init", str(seed), "--client", "fake/case", "--run-id", "../escape",
                  expected=2)["error"]["code"] == "arguments"
    assert invoke("init", str(seed), expected=2)["error"]["code"] == "arguments"
    assert not Path(cl.out_dir).exists()
