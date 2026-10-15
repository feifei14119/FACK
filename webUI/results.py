"""Read-only presentation of run, paired-comparison and archived evidence."""
import json
import math
from pathlib import Path
import re
import statistics

from tools.tune_run_report import snapshot_report
from webUI.workloads import extract_workload, from_manifest, read_json


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def median(values):
    values = list(values)
    return statistics.median(values) if values and all(number(v) and v > 0 for v in values) else None


def target(data, client_name):
    """Use recorded identity; never substitute today's manifest for a past run."""
    manifest = data.get("manifest") or {}
    contract = manifest.get("evaluation_contract") or data.get("contract") or {}
    recorded = data.get("target") or {}
    spec = recorded.get("client") or contract.get("client") or data.get("client") or client_name
    resources = (contract.get("client_identity") or {}).get("resources") or {}
    original = resources.get("original_co") or {}
    provenance = (data.get("input_provenance") or {}).get("source") or {}
    co = recorded.get("co") or original.get("path") or provenance.get("path")
    if co and not str(co).endswith(".co"):
        co = None
    arch = recorded.get("gfx") or (data.get("device") or {}).get("arch")
    if not arch:
        match = re.search(r"(?:^|[/ :\-])(gfx[0-9a-f]+)(?:$|[/ :])", str(co or "") + "/" + spec)
        arch = match[1] if match else None
    return {"client": spec, "gfx": arch, "co": co,
            "symbol": recorded.get("symbol") or contract.get("kernel")}


def metric(label, baseline, candidate, analysis=None, unit="µs"):
    a = analysis or {}
    ratio = a.get("median_ratio")
    low, high = a.get("lower_ratio_bound"), a.get("upper_ratio_bound")
    def percent(value):
        value = (value - 1) * 100 if number(value) else None
        return value if number(value) else None
    return {"label": label, "unit": unit, "baseline": baseline if number(baseline) and baseline > 0 else None,
            "candidate": candidate if number(candidate) and candidate > 0 else None,
            "gain_pct": percent(ratio), "lower_gain_pct": percent(low), "upper_gain_pct": percent(high),
            "bounds_label": "单侧统计界限", "verdict": a.get("verdict"), "pairs": a.get("pairs")}


def base(path, repo, kind, data, client_name):
    return {"id": str(path.relative_to(repo)), "source": str(path.relative_to(repo)),
            "title": data.get("run_id") or path.parent.name, "kind": kind,
            "target": target(data, client_name), "status": "not_finalized", "selected": None,
            "candidate": None, "metrics": [], "notes": [], "updated": path.stat().st_mtime,
            "workload": extract_workload(data, repo)}


def run_result(directory, repo, client_name):
    # Shared report checks manifest/archive/final integrity. It does not create
    # report files or overwrite exports, and does not trust a stale report.json.
    data = snapshot_report(directory)
    row = base(directory / "state.json", repo, "run", data, client_name)
    row["phase"] = data["phase"]
    row["screening"] = {"best": (data.get("screening_best") or {}).get("screen_score"),
                        "confirmed": (data.get("confirmed_best") or {}).get("screen_score")}
    if not row["target"]["gfx"]:
        original = next((c for c in data["candidates"] if c["id"] == "original" and c["integrity"] == "verified"), None)
        if original:
            source = (directory / original["archive_path"]).read_text()
            match = re.search(r'\.amdgcn_target\s+"[^"\n]*?\b(gfx[0-9a-f]+)', source)
            if match:
                row["target"]["gfx"] = match[1]
    final = data.get("final_result")
    if data["integrity_errors"]:
        row.update(status="invalid", notes=data["integrity_errors"])
        return row
    if not final:
        row["notes"].append("尚未完成最终验证；筛选最高分不代表最终采用。")
        return row
    row["status"] = final["status"]
    row["selected"] = (data.get("selected") or {}).get("id")
    comparison = data["comparisons"].get(final.get("comparison_id")) or {}
    row["candidate"] = comparison.get("candidate_id")
    if comparison.get("status") == "completed" and comparison.get("analysis"):
        pairs = comparison["pairs"]
        throughput = row["target"]["client"].split("/")[0] in ("aiter", "poc_kl")
        row["metrics"].append(metric("最终配对 · client score",
            median(p["scores"].get("reference") for p in pairs),
            median(p["scores"].get("candidate") for p in pairs), comparison["analysis"], "TFLOPS" if throughput else "score"))
        if throughput:
            times = {}
            for side in ("reference", "candidate"):
                times[side] = median((data["batches"][p["batches"][side]]["measurement"].get("samples") or [{}])[0]
                                    .get("result", {}).get("time_us") for p in pairs)
            if all(v is not None for v in times.values()):
                row["metrics"].append(metric("最终配对 · client 时间", times["reference"], times["candidate"], comparison["analysis"]))
        else:
            row["notes"].append("score 使用 client 的 tflops 字段；该 client 未声明吞吐量单位。")
    else:
        row["notes"].append("没有完整的最终配对测量，未生成最终性能提升。")
    if final["status"] == "original_retained":
        row["notes"].append("最终保留 original；表中候选对比不代表候选已采用。")
    return row


def paired_result(path, repo, data, client_name, archived=False):
    row = base(path, repo, "archive" if archived else "comparison", data, client_name)
    row["status"] = "comparison_only" if data.get("status") == "completed" or archived else data.get("status", "running")
    row["title"] = path.stem if archived else path.parent.name
    hashes = data.get("assemblies_sha256") or {k: v.get("sha256") for k, v in data.get("assemblies", {}).items()}
    if hashes.get("reference") and hashes.get("reference") == hashes.get("candidate"):
        row["notes"].append("两侧汇编相同：这是流程自检，不是调优收益。")
        if row["status"] == "comparison_only":
            row["status"] = "self_comparison"
    row["notes"].append("固定两份代码的比较，不自动推荐或采用候选；HIP graph 与 op_test 分别统计。")
    if data.get("error"):
        row["notes"].append(str(data["error"]))
    if row["status"] not in ("comparison_only", "self_comparison"):
        return row
    for label, a in data.get("results", {}).items():
        row["metrics"].append(metric(label, a.get("reference_median_us"), a.get("candidate_median_us"), a))
    return row


def historical_result(path, repo, data, client_name):
    row = base(path, repo, "archive", data, client_name)
    row.update(title=path.stem, status=data.get("outcome", "comparison_only"))
    if row["status"] == "original_retained":
        row["selected"] = "original"
    labels = {"graph": "HIP graph", "constant": "op_test:constant/constant", "uniform": "op_test:uniform/auto"}
    for label, a in data.get("comparison", {}).items():
        m = metric(labels.get(label, label), a.get("baseline_median_us"), a.get("candidate_median_us"))
        bounds = a.get("bootstrap95_gain_pct") or [None, None]
        m.update(gain_pct=a.get("paired_median_gain_pct"), lower_gain_pct=bounds[0], upper_gain_pct=bounds[1],
                 bounds_label="Bootstrap 95% 区间", pairs=len((a.get("times_us") or {}).get("baseline", [])))
        row["metrics"].append(m)
    row["notes"].append("归档实测结果；仅代表记录中的机器、shape 和环境。")
    return row


def validation_result(path, repo, data, client_name):
    request = read_json(path.with_name("request.json"), repo)
    runner = (data.get("detail") or {}).get("runner") or {}
    if runner and (runner.get("co_sha256") != request.get("co_sha256") or runner.get("symbol") != request.get("symbol")):
        raise ValueError("validation report/request identity mismatch")
    row = base(path, repo, "validation", data, client_name)
    row["target"] = {"client": client_name + "/hsa/" + request["arch"], "gfx": request["arch"],
                     "co": request["co"], "symbol": request["symbol"]}
    row["workload"] = from_manifest(request, repo)
    row["workload"]["dispatch_status"] = "verified" if runner.get("dispatch_check", {}).get("correct") is True else "not_checked"
    valid = data.get("compiled") is True and data.get("correct") is True and (
        data.get("detail", {}).get("build_evidence", {}).get("status") == "consistent")
    row["status"] = "validation_passed" if valid else "validation_failed"
    row["notes"].append("单次 client 验证；不是原始/候选独立配对收益，也不代表完成调优。")
    if valid and number(data.get("time_us")):
        row["measurement"] = {"time_us": data["time_us"]}
    if data.get("detail", {}).get("error"):
        row["notes"].append(str(data["detail"]["error"]))
    return row


def legacy_result(path, repo, data, client_name):
    row = base(path, repo, "screening", data, client_name)
    row.update(title=path.name, status="screening_only")
    best = data.get("screening_best") or data.get("best") or {}
    row["screening"] = {"best": best.get("tflops"), "baseline": best.get("baseline_tflops")}
    row["notes"].append("旧版筛选汇总，没有最终独立验证；缺失的 gfx/.co 不从当前配置猜测。")
    return row


def campaign_results(repo):
    """Present synchronized measurements with their recorded workload only."""
    from webUI.campaigns import read_campaigns
    synced = read_campaigns(repo)
    rows = []
    for campaign in synced["campaigns"]:
        for kernel in campaign["kernels"]:
            evidence = kernel.get("metrics") or {}
            if not evidence:
                continue
            match = re.search(r"gfx[0-9a-f]+", campaign.get("campaign_id", ""))
            arch = campaign.get("arch") or (match[0] if match else None)
            final = evidence.get("final") or {}
            decision = evidence.get("campaign_decision") or final.get("status") or "not_finalized"
            if decision in ("confirmed_gain", "candidate_adopted", "candidate_selected"):
                decision = "final_recommended" if evidence.get("valid_for_adoption") is True else "not_finalized"
            row = {"id": campaign["campaign_id"] + "/" + (kernel["workload"].get("id") or kernel.get("run_id") or kernel["co"]),
                "source": campaign["snapshot_path"], "title": kernel.get("run_id") or kernel["co"],
                "kind": "campaign", "target": {"client": "aiter/hsa/" + arch if arch else "aiter",
                    "gfx": arch, "co": kernel["co"], "symbol": kernel.get("symbol")},
                "workload": kernel["workload"], "status": decision,
                "selected": final.get("selected_id"), "metrics": [], "notes": [
                    "远端任务快照：" + campaign["campaign_id"]] + ([kernel["reason"]] if kernel.get("reason") else []),
                "artifacts": evidence.get("selected_artifact") or kernel.get("artifacts"),
                "updated": Path(campaign["snapshot_path"]).stat().st_mtime}
            if evidence.get("valid_for_adoption") is False:
                row["status"] = "invalid"
                row["notes"].append("候选验证失败；历史配对数值不计入有效收益。")
            else:
                for paired in evidence.get("paired_results", []):
                    if paired.get("stage") != "final" or not (paired.get("scope") == "independent_paired" or paired.get("independent") is True):
                        continue
                    analysis = {"median_ratio": 1 + paired["gain_pct"] / 100 if number(paired.get("gain_pct")) else None,
                        "lower_ratio_bound": paired.get("ratio_lower_bound"), "upper_ratio_bound": paired.get("ratio_upper_bound"),
                        "verdict": paired.get("verdict"), "pairs": paired.get("pairs")}
                    row["metrics"].append(metric("最终配对 · " + paired.get("method", "未记录"),
                        paired.get("reference_median_us"), paired.get("candidate_median_us"), analysis))
            screen = evidence.get("original_screen") or {}
            if screen.get("correct") is True:
                row["screening"] = {"baseline": screen.get("tflops"), "baseline_time_us": screen.get("time_us")}
            rows.append(row)
    return {"results": rows, "errors": synced["errors"]}


def read_results(repo, client_names):
    repo = Path(repo).resolve()
    rows, errors = [], []

    def reject_constant(value):
        raise ValueError("non-finite JSON number: " + value)

    def read(path, kind, client_name):
        try:
            # Only known result locations; never recurse into JIT caches or clones.
            if repo not in path.resolve().parents:
                raise ValueError("result path is outside repository")
            if kind == "run":
                rows.append(run_result(path.parent, repo, client_name))
                return
            data = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
            if not isinstance(data, dict):
                raise ValueError("result must be an object")
            if kind == "screening":
                row = legacy_result(path, repo, data, client_name)
            elif kind == "comparison" or data.get("purpose") == "portable_workflow_same_seed_comparison":
                row = paired_result(path, repo, data, client_name, archived=kind == "archive")
            elif kind == "validation":
                row = validation_result(path, repo, data, client_name)
            elif kind == "archive" and "comparison" in data:
                row = historical_result(path, repo, data, client_name)
            else:
                return
            rows.append(row)
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, RuntimeError) as exc:
            errors.append({"source": str(path.relative_to(repo)), "error": str(exc)})

    for name in client_names:
        root = repo / "client" / name
        for pattern, kind in (("tune_out/runs/*/state.json", "run"),
                              ("tune_out/comparisons/*/comparison.json", "comparison"),
                              ("tune_out/eval-*/evaluation.json", "validation"),
                              ("tune_out/tune_result/*.summary.json", "screening"),
                              ("docs/validated-runs/*.json", "archive")):
            for path in sorted(root.glob(pattern)):
                read(path, kind, name)
    rows.sort(key=lambda r: (r["kind"] != "archive", r["status"] in ("final_recommended", "original_retained"),
                             r["updated"], r["id"]), reverse=True)
    return {"results": rows, "errors": errors}
