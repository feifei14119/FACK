"""Read-only reports of real controller transitions using CPU fake clients."""
import hashlib
import json
from pathlib import Path

import pytest

from agent.run import RunController
from tools.tune_run_report import export_report, main
from unittests.test_paired_validation import POLICY, evaluator
from unittests.test_session import _SYNTH
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, passed, prepare


def create(tmp_path, paired=False):
    return RunController.create(tmp_path / "run", _SYNTH, CONTRACT, perf_repeats=1,
                                eval_call_limit=100, final_eval_reserve=16 if paired else 0,
                                comparison_policy=POLICY if paired else None)


def read_report(run, **kwargs):
    result = export_report(run.directory, **kwargs)
    return result, json.loads(Path(result["json_path"]).read_text())


def measured_candidate(run):
    run.evaluate("original", FakeEvaluator(passed(100)))
    candidate = prepare(run)["candidate_id"]
    run.evaluate(candidate, FakeEvaluator(passed(1000)))
    return candidate


def assert_copy(item, run):
    data = Path(item["export_path"]).read_bytes()
    assert data == run.source(item["id"]).encode()
    assert hashlib.sha256(data).hexdigest() == item["sha256"]


def test_high_screen_is_not_confirmed_or_recommended(tmp_path):
    run = create(tmp_path)
    candidate = measured_candidate(run)
    before = (run.directory / "state.json").read_bytes()
    result, report = read_report(run)
    assert (run.directory / "state.json").read_bytes() == before
    assert report["screening_best"]["id"] == candidate
    assert_copy(report["screening_best"], run)
    assert report["confirmed_best"] is None
    assert report["recommendation"] is None
    assert report["selected"] is None
    assert report["final_result"] is None
    assert report["attempts"] == run.status()["state"]["attempts"]
    assert "no recommendation" in Path(result["markdown_path"]).read_text()
    assert not (run.directory / "report/selected.s").exists()


def test_confirmed_incumbent_requires_final_before_recommendation(tmp_path):
    run = create(tmp_path, paired=True)
    candidate = measured_candidate(run)
    run.confirm(candidate, evaluator())
    _, report = read_report(run)
    assert report["confirmed_best"]["id"] == candidate
    assert_copy(report["confirmed_best"], run)
    assert report["selected"] is report["recommendation"] is None
    run.finalize(evaluator("final"))
    result, report = read_report(run)
    assert report["recommendation"]["id"] == candidate
    assert report["selected"]["id"] == candidate
    assert_copy(report["selected"], run)
    assert report["final_vs_original"]["median_ratio"] == pytest.approx(1.1)
    assert report["final_vs_normalized"] is None
    assert len(report["comparisons"]) == 2
    assert len(report["attempts"]) == 34
    assert not result["integrity_errors"]


def test_failed_final_exports_original_not_confirmed_incumbent(tmp_path):
    run = create(tmp_path, paired=True)
    candidate = measured_candidate(run)
    run.confirm(candidate, evaluator())
    run.finalize(evaluator("final", candidate=99))
    _, report = read_report(run)
    assert report["confirmed_best"]["id"] == candidate
    assert report["final_result"]["status"] == "original_retained"
    assert report["recommendation"] is None
    assert report["selected"]["id"] == "original"
    assert_copy(report["selected"], run)


def test_untimed_original_fallback_is_explicit(tmp_path):
    run = create(tmp_path, paired=True)
    run.finalize(FakeEvaluator())
    _, report = read_report(run)
    assert report["selected"]["id"] == "original"
    assert report["final_result"]["original_screen_status"] == "not_measured"
    assert report["recommendation"] is None


def test_inflight_attempt_reports_without_recovery_or_refund(tmp_path):
    run = create(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        run.evaluate("original", FakeEvaluator(KeyboardInterrupt()))
    _, report = read_report(run)
    assert report["used"]["eval_calls"] == 1
    assert report["failures"][0]["status"] == "running"
    assert next(iter(report["attempts"].values()))["status"] == "running"
    assert report["recommendation"] is None


def test_latest_failed_screen_does_not_reuse_older_high_score(tmp_path):
    run = create(tmp_path)
    candidate = measured_candidate(run)
    run.evaluate(candidate, FakeEvaluator(RuntimeError("fake failure")), repeat=True)
    _, report = read_report(run)
    assert report["screening_best"]["id"] == "original"
    assert report["failures"]


def test_corrupt_archive_withholds_final_and_removes_stale_copy(tmp_path, capsys):
    run = create(tmp_path, paired=True)
    candidate = measured_candidate(run)
    run.confirm(candidate, evaluator())
    run.finalize(evaluator("final"))
    result, report = read_report(run)
    selected = Path(result["selected_path"])
    artifact = run.directory / report["selected"]["archive_path"]
    artifact.write_bytes(b"corrupted")
    assert main([str(run.directory)]) == 2
    cli = json.loads(capsys.readouterr().out)
    report = json.loads(Path(cli["json_path"]).read_text())
    assert report["integrity_errors"]
    assert report["recommendation"] is None
    assert report["selected"] is None
    assert not selected.exists()


def test_manifest_change_is_not_reported_as_valid(tmp_path, capsys):
    run = create(tmp_path)
    path = run.directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["budget"]["eval_call_limit"] = 100000
    path.write_text(json.dumps(manifest))
    assert main([str(run.directory)]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "manifest_mismatch"


def test_outside_archive_is_rejected(tmp_path):
    run = create(tmp_path)
    outside = tmp_path / "outside.s"
    outside.write_text(_SYNTH)
    state_path = run.directory / "state.json"
    state = json.loads(state_path.read_text())
    state["candidates"]["original"]["artifact"]["path"] = str(outside)
    state_path.write_text(json.dumps(state))
    result, report = read_report(run)
    assert any("outside run" in error for error in result["integrity_errors"])
    assert report["selected"] is None


def test_provenance_is_annotation_with_digest_check(tmp_path):
    run = create(tmp_path)
    data = b"fake code object, no ISA conversion in this test"
    (run.directory / "inputs").mkdir()
    (run.directory / "inputs/original.co").write_bytes(data)
    sidecar = {"source": {"archive": "inputs/original.co", "sha256": hashlib.sha256(data).hexdigest()},
               "assembly_sha256": run.status()["manifest"]["original_sha256"],
               "conversion": {"original_co_measurement": "not_measured"}}
    (run.directory / "input_provenance.json").write_text(json.dumps(sidecar))
    _, report = read_report(run)
    assert report["input_provenance"]["archive_integrity"] == "verified"
    assert report["input_provenance"]["conversion"]["original_co_measurement"] == "not_measured"
    (run.directory / "inputs/original.co").write_bytes(b"changed")
    result, report = read_report(run)
    assert report["input_provenance"]["archive_integrity"] == "invalid"
    assert result["integrity_errors"]


def test_custom_json_path_keeps_evidence_and_markdown(tmp_path):
    run = create(tmp_path)
    result, report = read_report(run, json_path=tmp_path / "custom/results.jsonl")
    assert result["markdown_path"].endswith("custom/results.md")
    assert report["manifest"]["evaluation_contract"]["params"] == CONTRACT["params"]


def test_report_destinations_cannot_overwrite_authority_or_selected_copy(tmp_path):
    run = create(tmp_path)
    before = (run.directory / "state.json").read_bytes()
    for destination in (run.directory / "state.json", run.directory / "manifest.json",
                        run.directory / "report/selected.s"):
        with pytest.raises(ValueError):
            export_report(run.directory, json_path=destination)
    with pytest.raises(ValueError):
        export_report(run.directory, out=run.directory)
    assert (run.directory / "state.json").read_bytes() == before


def test_schema_one_reports_and_ledger_remain_read_only(tmp_path):
    from agent.run import _atomic_json, _digest
    from unittests.test_tuning_run import assert_error
    run = create(tmp_path)
    candidate = measured_candidate(run)
    snapshot = run.status()
    manifest, state = snapshot["manifest"], snapshot["state"]
    manifest["schema_version"] = state["schema_version"] = 1
    manifest.pop("comparison_policy")
    manifest.pop("search_policy")
    for key in ("comparisons", "confirmation_count", "incumbent_evidence_id", "phase", "final_result"):
        state.pop(key, None)
    for table in ("batches", "attempts"):
        for item in state[table].values():
            item.pop("stage", None)
    state["manifest_sha256"] = _digest(manifest)
    _atomic_json(run.directory / "manifest.json", manifest)
    _atomic_json(run.directory / "state.json", state)
    before = (run.directory / "state.json").read_bytes()
    _, report = read_report(run)
    assert report["screening_best"]["id"] == candidate
    assert run.ledger()["final_result"] is None
    assert report["phase"] == "legacy_read_only"
    assert (run.directory / "state.json").read_bytes() == before
    assert_error("schema_upgrade_required", lambda: run.observe())


def test_export_cannot_overwrite_history_authority_via_external_path(tmp_path):
    run = create(tmp_path)
    history = RunController.create(tmp_path / "history", _SYNTH, CONTRACT)
    state_path = history.directory / "state.json"
    before = state_path.read_bytes()
    with pytest.raises(ValueError, match="another run"):
        export_report(run.directory, json_path=state_path)
    alias = tmp_path / "history-alias"
    alias.symlink_to(history.directory, target_is_directory=True)
    with pytest.raises(ValueError, match="another run"):
        export_report(run.directory, out=alias / "exports")
    assert state_path.read_bytes() == before


def test_default_report_directory_cannot_alias_another_run(tmp_path):
    run = create(tmp_path)
    history = RunController.create(tmp_path / "history", _SYNTH, CONTRACT)
    (history.directory / "report").mkdir()
    (run.directory / "report").symlink_to(history.directory / "report", target_is_directory=True)
    with pytest.raises(ValueError, match="another run"):
        export_report(run.directory)
    assert not (history.directory / "report/report.json").exists()
