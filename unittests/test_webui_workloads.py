"""UI provenance and action regression tests; no GPU or remote commands."""
import hashlib
import json
from pathlib import Path

import pytest

from webUI import workloads, workflow, results


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def test_historical_shape_is_shown_without_inventing_csv(tmp_path):
    result = workloads.extract_workload({"metrics": {"shape": {"m": 192, "n": 1280, "k": 1024}}}, tmp_path)
    assert result["inputs"] == {"m": 192, "n": 1280, "k": 1024}
    assert result["csv"] == []
    assert result["selection"] == "recorded_inputs"


def test_frozen_manifest_provenance_and_recorded_cli_override(tmp_path):
    manifest = write(tmp_path / "client/aiter/tune_out/p/task.json", {
        "inputs": {"m": 192, "n": 1280, "k": 1024}, "dispatch": {
            "workload_id": "workload-1", "cu_num": 80, "reference": {
                "source": {"path": "aiter/configs/model.csv", "sha256": "abc"}, "line": 37}}})
    resource = {"path": str(manifest), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
    data = {"contract": {"client_identity": {"resources": {"manifest": resource}}, "params": ["--m", "256"]}}
    value = workloads.extract_workload(data, tmp_path)
    assert value["inputs"]["m"] == 256
    assert value["csv"] == [{"path": "aiter/configs/model.csv", "line": 37, "sha256": "abc"}]
    assert value["id"] == "workload-1"
    manifest.write_text('{"inputs":{"m":999}}')
    changed = workloads.extract_workload(data, tmp_path)
    assert changed["inputs"] == {"m": 256}  # recorded CLI survives; today's defaults do not
    assert changed["csv"] == [] and changed["notes"]


def test_frozen_client_profile_preserves_workload_when_manifest_is_unavailable(tmp_path):
    profile = {'arch': 'gfx942', 'workload': {'co': 'selected.co', 'symbol': 'kernel',
        'inputs': {'m': 32, 'n': 8192, 'k': 7168}, 'dispatch': {'workload_id': 'id',
        'reference': {'source': {'path': 'tuned.csv', 'sha256': 'sha'}, 'line': 1152}}}}
    data = {'contract': {'client': 'aiter/hsa/gfx942', 'agent_profile': profile,
            'client_identity': {'resources': {'manifest': {'path': 'missing.json', 'sha256': 'old'}}}}}
    value = workloads.extract_workload(data, tmp_path)
    assert value['inputs'] == profile['workload']['inputs']
    assert value['csv'] == [{'path': 'tuned.csv', 'sha256': 'sha', 'line': 1152}]
    assert value['id'] == 'id' and value['selection'] == 'dispatch_csv'
    assert results.target(data, 'aiter') == {'client': 'aiter/hsa/gfx942', 'gfx': 'gfx942',
                                          'co': 'selected.co', 'symbol': 'kernel'}


def test_sdk_command_forwards_comparison_policy_before_client_params(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from webUI import server
    monkeypatch.setattr(server, 'REPO', str(tmp_path))
    monkeypatch.setattr(server._clients, 'resolve', lambda spec: SimpleNamespace(spec=spec))
    (tmp_path/'seed.s').write_text('seed')
    write(tmp_path/'policy.json', {})
    params = {'seed': 'seed.s', 'client': 'custom/case', 'policy': 'policy.json',
              'search_policy': 'policy.json', 'params': 'size=123'}
    _, argv, _, _ = server.build_command('tune', params)
    assert argv[argv.index('--comparison-policy') + 1] == str(tmp_path/'policy.json')
    assert argv.index('--comparison-policy') < argv.index('--')
    assert argv[argv.index('--search-policy') + 1] == str(tmp_path/'policy.json')
    assert argv.index('--search-policy') < argv.index('--')
    assert argv[argv.index('--') + 1:] == ['size=123']
    params['policy'] = 'missing.json'
    with pytest.raises(ValueError, match='策略文件不存在'):
        server.build_command('tune', params)


def test_old_dispatch_line_recovery_requires_unchanged_source_and_exact_row(tmp_path):
    source = tmp_path / "client/aiter/upstream/aiter/configs/tuned.csv"
    source.parent.mkdir(parents=True)
    source.write_text("M,N,K,kernelName\n192,1280,1024,selected\n192,1536,1024,selected\n")
    binding = {"sources": [{"path": "aiter/configs/tuned.csv", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
               "row": {"M": "192", "N": "1536", "K": "1024", "kernelName": "selected"}}
    assert workloads.csv_references(binding, tmp_path)[0]["line"] == 3
    source.write_text("M,N,K,kernelName\n192,1536,1024,selected\n")
    assert workloads.csv_references(binding, tmp_path) == []


def test_embedded_measurement_metadata_survives_missing_manifest(tmp_path):
    recorded = {"id": "task", "inputs": {"m": 192, "n": 1280, "k": 1024},
                "csv": [{"path": "deployment.csv", "line": 9}], "selection": "dispatch_csv"}
    data = {"records": [{"result": {"detail": {"runner": {"workload": recorded,
            "dispatch_check": {"correct": True}}}}}]}
    assert workloads.extract_workload(data, tmp_path)["csv"][0]["line"] == 9
    other = {**recorded, "inputs": {"m": 128}}
    data["records"].append({"result": {"detail": {"runner": {"workload": other}}}})
    assert workloads.extract_workload(data, tmp_path)["selection"] == "inconsistent"


def plan_fixture(tmp_path):
    refs = [{"workload_id": name, "family": "a8w8", "status": "ready_for_validation", "reason": "validate",
             "row": {"M": "192", "N": n, "K": "1024"}, "inputs": {"m": 192, "n": int(n), "k": 1024},
             "source": {"path": "aiter/configs/a8w8.csv", "sha256": "abc"}, "line": line,
             "matches": [{"co": "i8gemm/same.co"}]} for name, n, line in [("a", "1280", 5), ("b", "1536", 20)]]
    return write(tmp_path / "client/aiter/tune_out/dispatch-test/plan.json", {
        "arch": "gfx942", "cu_num": 80, "references": refs,
        "tasks": [{"task_id": r["workload_id"], "manifest": r["workload_id"] + ".json"} for r in refs],
        "co_to_workloads": {"i8gemm/same.co": ["a", "b"]}})


def test_plan_api_preserves_multiple_shapes_and_exact_csv_line(tmp_path):
    path = plan_fixture(tmp_path)
    before = path.read_bytes()
    data = workloads.read_plans(tmp_path)
    assert not data["errors"]
    plan = data["plans"][0]
    assert plan["tasks"] == 2 and plan["co_count"] == 1
    assert [r["workload"]["csv"][0]["line"] for r in plan["rows"]] == [5, 20]
    assert len({r["id"] for r in plan["rows"]}) == 2
    assert path.read_bytes() == before


def test_progress_joins_by_workload_id_not_co(tmp_path):
    plan_fixture(tmp_path)
    write(tmp_path / 'client/aiter/tune_out/comparisons/pair/comparison.json', {
        'status': 'completed', 'client': 'aiter/hsa/gfx942', 'workload': {
            'id': 'a', 'inputs': {'m': 192, 'n': 1280, 'k': 1024}, 'csv': []}, 'results': {}})
    rows = workloads.read_plans(tmp_path)['plans'][0]['rows']
    assert rows[0]['progress']['status'] == 'comparison_only'
    assert rows[1]['progress']['status'] == 'not_started'


def test_validation_results_show_inputs_without_inventing_comparison(tmp_path):
    root = tmp_path / 'client/aiter/tune_out/eval-check'
    write(root / 'request.json', {'arch': 'gfx942', 'co': 'i8gemm/test.co', 'symbol': 'kernel',
        'co_sha256': 'abc', 'inputs': {'m': 192, 'n': 1280, 'k': 1024}, 'validation_hook': True,
        'dispatch': {'workload_id': 'shape', 'reference': {'source': {'path': 'tuned.csv'}, 'line': 12}}})
    write(root / 'evaluation.json', {'compiled': True, 'correct': True, 'time_us': 12.0, 'detail': {
        'build_evidence': {'status': 'consistent'}, 'runner': {'arch': 'gfx942', 'symbol': 'kernel',
        'co_sha256': 'abc', 'correct': True, 'time_us': 12.0, 'loader_observed': True, 'op_test': {'correct': True}}}})
    result = results.read_results(tmp_path, ['aiter'])['results'][0]
    assert result['kind'] == 'validation' and result['status'] == 'validation_passed'
    assert result['workload']['csv'][0]['line'] == 12
    assert result['metrics'] == [] and result['selected'] is None
    path = root / 'evaluation.json'
    failed = json.loads(path.read_text())
    failed['correct'] = None
    failed['detail']['build_evidence']['status'] = 'changed'
    write(path, failed)
    result = results.read_results(tmp_path, ['aiter'])['results'][0]
    assert result['status'] == 'validation_failed'
    assert 'measurement' not in result  # raw runner success cannot override client failure


def test_outside_plan_symlink_is_rejected(tmp_path):
    outside = write(tmp_path / "outside.json", {})
    repo = tmp_path / "repo"
    dest = repo / "client/aiter/tune_out/dispatch-p/plan.json"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(outside)
    assert workloads.read_plans(repo)["errors"]


@pytest.fixture
def task(tmp_path, monkeypatch):
    root = tmp_path / "client/aiter/tune_out/dispatch-test"
    root.mkdir(parents=True)
    seed = root / "a.s"
    seed.write_text("seed")
    manifest = root / "a.json"
    manifest.write_text("{}")
    monkeypatch.setattr(workflow, "resolve_task", lambda *args: ({"co": "i8gemm/same.co"}, manifest, seed))
    return {"plan": "client/aiter/tune_out/dispatch-test/plan.json", "task_id": "a", "python": "/opt/venv/bin/python3",
            "gpu": "GPU-example", "candidate": str(seed), "m": "999", "params": "--m 999"}


@pytest.mark.parametrize("action", ["dispatch_prepare", "dispatch_validate", "dispatch_init", "dispatch_evaluate", "dispatch_compare", "dispatch_assess"])
def test_actions_use_workload_manifest_and_never_override_shapes(tmp_path, task, action):
    title, argv, cwd, env = workflow.command(action, task, tmp_path)
    assert "poc_kl" not in " ".join(argv)
    assert "--m" not in argv and "999" not in argv
    assert cwd == str(tmp_path)
    if action in ("dispatch_validate", "dispatch_evaluate", "dispatch_compare"):
        assert env == {"HIP_VISIBLE_DEVICES": "GPU-example"}
        assert argv[argv.index("--client") + 1] == "aiter/hsa/gfx942"
        assert "--manifest" in argv[argv.index("--") + 1:]


def test_dispatch_init_forwards_search_provider_policy(tmp_path, task):
    task['search_policy'] = str(write(tmp_path/'search.json', {'candidate_providers': ['generic']}))
    _, argv, _, _ = workflow.command('dispatch_init', task, tmp_path)
    assert argv[argv.index('--search-policy') + 1] == task['search_policy']
    assert argv.index('--search-policy') < argv.index('--')


def test_gpu_action_requires_explicit_device_or_existing_visibility(tmp_path, task, monkeypatch):
    for key in ("HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES"):
        monkeypatch.delenv(key, raising=False)
    task.pop("gpu")
    with pytest.raises(ValueError, match="GPU"):
        workflow.command("dispatch_validate", task, tmp_path)


def test_campaign_result_shape_and_invalid_gain_remain_distinct(tmp_path, monkeypatch):
    from webUI import campaigns
    path = write(tmp_path / "snapshot.json", {})
    snapshot = {"campaign_id": "aiter-gfx942-run", "snapshot_path": str(path), "kernels": [{
        "co": "same.co", "run_id": "r", "workload": {"inputs": {"m": 192}, "csv": []},
        "metrics": {"valid_for_adoption": False, "campaign_decision": "confirmed_gain",
                    "paired_results": [{"stage": "final", "scope": "independent_paired", "gain_pct": 99}]}}]}
    monkeypatch.setattr(campaigns, "read_campaigns", lambda repo: {"campaigns": [snapshot], "errors": []})
    result = results.campaign_results(tmp_path)["results"][0]
    assert result["workload"]["inputs"]["m"] == 192
    assert result["status"] == "invalid" and result["metrics"] == []
