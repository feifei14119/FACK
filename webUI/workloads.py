"""Read workload provenance and dispatch plans without importing GPU clients.

Historical input metadata must come from the record or a hash-matching frozen
manifest. Never reverse-join an old result to today's dispatch tables.
"""
import csv
import hashlib
import json
from pathlib import Path
import shlex


def read_json(path, repo, limit=32 * 1024 * 1024):
    path = Path(path).resolve()
    path.relative_to(Path(repo).resolve())
    if path.stat().st_size > limit:
        raise ValueError("JSON exceeds size limit")
    value = json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def local_record_path(value, repo):
    """Translate only repository-relative or recorded /client/ paths locally."""
    path = Path(value)
    repo = Path(repo).resolve()
    if path.is_absolute() and repo not in path.resolve().parents:
        marker = "/client/"
        if marker not in str(path):
            raise ValueError("record is outside repository")
        path = Path("client") / str(path).split(marker, 1)[1]
    path = path if path.is_absolute() else repo / path
    path.resolve().relative_to(repo)
    return path


def csv_references(binding, repo):
    reference = binding.get("reference") or {}
    if reference.get("source") and reference.get("line"):
        return [dict(reference["source"], line=reference["line"])]
    # Early dispatch manifests recorded full rows + source hashes, but no line.
    # Recover it only from exactly those unchanged files and that exact row.
    row = binding.get("row") or {}
    found = []
    for source in binding.get("sources", []):
        name = source.get("path", "")
        if not name or Path(name).is_absolute():
            continue
        path = Path(repo) / "client/aiter/upstream" / name
        try:
            path.resolve().relative_to(Path(repo).resolve())
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != source.get("sha256"):
                continue
            reader = csv.DictReader(payload.decode("utf-8-sig").splitlines())
            for item in reader:
                if item and all(str(row.get(k)) == str(v).strip() for k, v in item.items()):
                    found.append(dict(source, line=reader.line_num))
        except (OSError, ValueError, UnicodeError):
            continue
    return found


def from_manifest(data, repo):
    binding = data.get("dispatch") or {}
    return {"id": binding.get("workload_id"), "inputs": data.get("inputs") or {},
            "csv": csv_references(binding, repo), "entrypoint": binding.get("entrypoint"),
            "cu_num": binding.get("cu_num"), "selection": "dispatch_csv" if binding else "explicit_manifest",
            "dispatch_status": "not_checked", "notes": []}


def extract_workload(data, repo):
    embedded = data.get("workload")
    if isinstance(embedded, dict) and "inputs" in embedded:
        return embedded
    contract = (data.get("manifest") or {}).get("evaluation_contract") or data.get("contract") or {}
    result = {"id": None, "inputs": {}, "csv": [], "selection": "unrecorded",
              "dispatch_status": "not_recorded", "notes": []}
    frozen_workload = (contract.get("agent_profile") or {}).get("workload")
    if isinstance(frozen_workload, dict) and "inputs" in frozen_workload:
        result = from_manifest(frozen_workload, repo)
        if not frozen_workload.get("dispatch"):
            result.update(selection=frozen_workload.get("source", "recorded_inputs"),
                          id=frozen_workload.get("id"), csv=frozen_workload.get("csv", []))
    resource = ((contract.get("client_identity") or {}).get("resources") or {}).get("manifest") or {}
    if not frozen_workload and resource.get("path") and resource.get("sha256"):
        try:
            path = local_record_path(resource["path"], repo)
            if hashlib.sha256(path.read_bytes()).hexdigest() != resource["sha256"]:
                raise ValueError("历史 manifest 摘要不匹配")
            result = from_manifest(read_json(path, repo), repo)
        except (OSError, ValueError):
            result["notes"].append("历史 manifest 不可用或摘要不匹配；不使用当前配置补填。")
    # Runner metadata travels with measurement evidence, including remote runs.
    runners = [r.get("result", {}).get("detail", {}).get("runner", {}) for r in data.get("records", [])]
    for batch in (data.get("batches") or {}).values():
        runners.extend(s.get("result", {}).get("detail", {}).get("runner", {})
                       for s in (batch.get("measurement") or {}).get("samples", []))
    recorded = [r["workload"] for r in runners if isinstance(r.get("workload"), dict)]
    if recorded:
        unique = {json.dumps(r, sort_keys=True) for r in recorded}
        if len(unique) == 1:
            observed = dict(recorded[0])
            if observed.get("id") and observed.get("id") == result.get("id") and not observed.get("csv"):
                observed["csv"] = result.get("csv", [])
            result = observed
        else:
            return dict(result, inputs={}, csv=[], selection="inconsistent",
                        notes=["测量记录含不同 workload，不能合并为同一尺寸结果。"])
    elif not result["inputs"]:
        inputs = data.get("inputs") or data.get("shape") or (data.get("metrics") or {}).get("shape") or {}
        if isinstance(inputs, dict):
            result["inputs"] = inputs
    params = contract.get("params") or data.get("params") or []
    if isinstance(params, str):
        params = shlex.split(params)
    # Historical explicit CLI overrides are stronger than manifest defaults.
    for i, token in enumerate(params):
        for dim in ("m", "n", "k"):
            value = params[i + 1] if token == "--" + dim and i + 1 < len(params) else (
                token.split("=", 1)[1] if token.startswith("--" + dim + "=") else None)
            if value is not None:
                try:
                    result["inputs"][dim] = int(value)
                except (ValueError, TypeError):
                    pass
    checks = [r["dispatch_check"] for r in runners if r.get("dispatch_check")]
    if checks:
        result["dispatch_status"] = "verified" if all(r.get("correct") is True for r in checks) else "failed"
    if result["inputs"] and result.get("selection") == "unrecorded":
        result["selection"] = "recorded_inputs"
    return result


def read_plans(repo):
    repo = Path(repo).resolve()
    plans, errors = [], []
    from webUI.results import read_results, campaign_results
    evidence = read_results(repo, ["aiter"])["results"] + campaign_results(repo)["results"]
    by_workload = {}
    for result in evidence:
        key = (result.get("workload") or {}).get("id")
        if key:
            by_workload.setdefault(key, []).append(result)
    for path in sorted(repo.glob("client/aiter/tune_out/*/plan.json"), reverse=True):
        try:
            data = read_json(path, repo)
            if not isinstance(data.get("references"), list) or not isinstance(data.get("tasks"), list):
                continue
            tasks = {t["task_id"]: t for t in data["tasks"]}
            rows = []
            for ref in data["references"]:
                key = ref["workload_id"]
                task = tasks.get(key)
                row = ref.get("effective_row") or ref.get("row") or {}
                inputs = ref.get("inputs") or {k: v for k, v in row.items() if k not in (
                    "kernelName", "kernelName1", "kernelName2", "us", "us1", "us2", "tflops", "bw")}
                rows.append({"id": key, "family": ref["family"], "status": ref["status"],
                    "reason": ref.get("reason"), "co": [m["co"] for m in ref.get("matches", [])],
                    "symbol": ref.get("symbol"), "backend": ref.get("backend"), "stage": ref.get("stage"),
                    "manifest": str(path.parent.relative_to(repo) / task["manifest"]) if task else None,
                    "seed": str(path.parent.relative_to(repo) / (key + ".s")) if task else None,
                    "workload": {"id": key, "inputs": inputs,
                        "csv": [dict(ref["source"], line=ref["line"])], "selection": "dispatch_csv",
                        "cu_num": data["cu_num"], "entrypoint": ref.get("entrypoint"),
                        "dispatch_status": "not_checked"}})
                related = sorted(by_workload.get(key, []), key=lambda r: (r["status"] in (
                    "final_recommended", "original_retained"), r.get("updated", 0)), reverse=True)
                rows[-1]["progress"] = {"status": related[0]["status"] if related else "not_started",
                    "records": len(related), "sources": [r["source"] for r in related]}
            plans.append({"id": str(path.relative_to(repo)), "name": path.parent.name,
                "arch": data["arch"], "cu_num": data["cu_num"], "counts": data.get("counts", {}),
                "tasks": len(tasks), "co_count": len(data.get("co_to_workloads", {})), "rows": rows,
                "families": data.get("families", {}), "unreferenced_co": data.get("unreferenced_co", []),
                "updated": path.stat().st_mtime})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append({"source": str(path.relative_to(repo)), "error": str(exc)})
    return {"plans": sorted(plans, key=lambda p: p["updated"], reverse=True), "errors": errors}


def resolve_task(repo, plan_name, task_id):
    repo = Path(repo).resolve()
    plan_path = local_record_path(plan_name, repo)
    plan_path.resolve().relative_to(repo / "client/aiter/tune_out")
    data = read_json(plan_path, repo)
    matches = [t for t in data["tasks"] if t["task_id"] == task_id]
    if len(matches) != 1:
        raise ValueError("请选择计划中可验证的唯一 workload")
    task = matches[0]
    manifest = (plan_path.parent / task["manifest"]).resolve()
    manifest.relative_to(plan_path.parent.resolve())
    from client.aiter.common import load_manifest
    config, _ = load_manifest(manifest, "gfx942")
    if config.get("dispatch", {}).get("workload_id") != task_id:
        raise ValueError("任务与冻结 manifest 不匹配")
    return config, manifest, plan_path.parent / (task_id + ".s")
