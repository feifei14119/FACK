"""Publish one final recommendation through the selected client; no GPU or model calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import client
from agent.history import _comparison
from agent.run import RunController, RunError
from tools.tune_run_report import _snapshot_report, _archive
from tools.result_publication import publish, atomic, json_bytes


def publication_plan(run_directory):
    run = RunController(run_directory)
    snapshot = run.status()
    manifest, state = snapshot["manifest"], snapshot["state"]
    profile = manifest["evaluation_contract"].get("agent_profile") or {}
    declaration = profile.get("publication")
    if not declaration:
        return None, "client_does_not_publish"
    final = state.get("final_result") or {}
    if final.get("status") != "final_recommended":
        return None, "no_final_recommendation"
    report = _snapshot_report(run, snapshot)
    if report["integrity_errors"] or not report["recommendation"]:
        raise ValueError("publication report integrity failed: " + str(report["integrity_errors"]))
    validation = profile.get("validation")
    if not validation:
        raise ValueError("publication requires a frozen metric validation contract")
    comparison = state["comparisons"][final["comparison_id"]]
    _comparison(manifest, state, state["comparisons"][state["incumbent_evidence_id"]])
    _comparison(manifest, state, comparison)
    methods = comparison.get("methods", {})
    if (set(methods) != set(validation["metrics"]) or
            any(m.get("verdict") != "confirmed_gain" or m["median_ratio"] <= 1 for m in methods.values()) or
            methods != final.get("methods")):
        raise ValueError("every required final metric must independently confirm a gain")
    cl = client.resolve(manifest["evaluation_contract"]["client"])
    if (declaration.get("mode") != "git_commit_push" or declaration.get("readme") != "README.md" or
            not declaration["output_dir"].startswith("client/" + cl.name + "/")):
        raise ValueError("invalid frozen publication destination")
    hook = getattr(cl.module, "publication_candidate", None)
    if not callable(hook):
        raise ValueError("selected client has no publication_candidate hook")
    artifact = hook(report)
    if artifact is None:
        return None, "identical_code_object"
    if hashlib.sha256(artifact["code_object"]).hexdigest() != artifact["co_sha256"]:
        raise ValueError("publication code-object digest mismatch")
    selected = state["candidates"][final["selected_id"]]["artifact"]
    assembly = _archive(run.directory, selected)
    started, finished = manifest["created_at"], final["finished_at"]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in (started, finished)) or finished < started:
        raise ValueError("invalid tuning timestamps")
    workload = profile["workload"]
    return dict(artifact, publication=declaration, client=cl.spec, run_id=manifest["run_id"],
                candidate_id=final["selected_id"], source_sha256=selected["sha256"],
                original_sha256=manifest["original_sha256"], assembly=assembly,
                workload={k: v for k, v in workload.items() if k != "manifest"},
                inputs_identity={"inputs": workload["inputs"], "symbol": workload.get("symbol")},
                methods=methods, comparison_policy=manifest["comparison_policy"],
                finished_at=datetime.fromtimestamp(finished, timezone.utc).isoformat(timespec="seconds"),
                duration_seconds=finished - started), None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="completed run; repeat explicitly to retry a failed push")
    args = parser.parse_args(argv)
    try:
        plan, reason = publication_plan(args.run)
        result = publish(REPO, plan) if plan else {"status": "skipped", "reason": reason}
        if plan:
            atomic(Path(args.run) / "publication.json", json_bytes(result))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (RunError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        result = {"error": {"code": "publication_failed", "message": str(exc)},
                  "recovery": "Inspect the existing commit and run tools/publish_run.py RUN again; no force push or automatic rebase."}
        if Path(args.run).is_dir():
            atomic(Path(args.run) / "publication.json", json_bytes(result))
        print(json.dumps(result, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
