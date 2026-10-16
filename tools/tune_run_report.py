"""Export a read-only persistent-run snapshot; never measure or infer promotion.

state.json is authoritative. SDK sidecars are provenance annotations only.
The selected assembly is exported only after a finalized result, and every
exported assembly is checked against the archived SHA-256 in that snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.run import RunController, RunError
from agent.ledger import ledger_snapshot
from harness.measurement import valid_score


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".report-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _archive(directory, artifact):
    path = (directory / artifact["path"]).resolve()
    if directory not in path.parents or not path.is_file():
        raise ValueError("archive is missing or outside run")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
        raise ValueError("archive SHA-256 mismatch")
    return data


def _latest_screen(state, candidate_id):
    batches = [b for b in state["batches"].values()
               if b["candidate_id"] == candidate_id and b.get("stage", "screen") == "screen"]
    return max(batches, key=lambda b: b["sequence"]) if batches else None


def _cell(value):
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report):
    final = report["final_result"]
    lines = ["# Persistent tuning run: " + report["run_id"], "",
             "- State revision: {} / phase: {}".format(report["state_revision"], report["phase"]),
             "- Confirmation: " + report["confirmation_status"],
             "- Final: " + (final["status"] if final else "not_performed; no recommendation"),
             "- Recommendation: " + (report["recommendation"]["id"] if report["recommendation"] else "none"),
             "- Selected copy: " + ((report["selected"]["export_path"] or "not exported") if report["selected"] else "none"),
             "- Environment still matches recorded engine/runtime: " + str(report["environment_matches"]),
             "- Budget used: " + json.dumps(report["used"], ensure_ascii=False),
             "- Frozen budget: " + json.dumps(report["manifest"]["budget"], ensure_ascii=False), "",
             "- Search policy: " + json.dumps(report["manifest"].get("search_policy"), ensure_ascii=False),
             "- Search progress: " + json.dumps(report["search"], ensure_ascii=False), "",
             "Screening scores, confirmed incumbent and final recommendation are separate evidence stages.",
             "A retained original is a fallback input, not a newly validated final winner.", "",
             "| candidate | parent | latest screen | score | SHA-256 | archive |",
             "|---|---|---|---|---|---|"]
    for candidate in report["candidates"]:
        lines.append("| " + " | ".join(_cell(candidate[k]) for k in
                     ("id", "parent_id", "screen_status", "screen_score", "sha256", "integrity")) + " |")
    lines.extend(["", "## Paired comparisons", "",
                  "| stage | candidate | reference | status | verdict | pairs | planned | stop | median ratio | estimate | one-sided lower bound |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"])
    for comparison in report["comparisons"].values():
        analysis = comparison.get("analysis") or {}
        cells = [comparison.get(k) for k in ("stage", "candidate_id", "reference_id", "status", "verdict")]
        cells += [analysis.get("pairs"), comparison.get("planned_pairs"), analysis.get("stop_reason")]
        cells += [analysis.get(k) for k in ("median_ratio", "estimate_ratio", "lower_ratio_bound")]
        lines.append("| " + " | ".join(map(_cell, cells)) + " |")
    declared = report["manifest"]["evaluation_contract"].get("agent_profile", {})
    if declared:
        lines.extend(["", "## Client and architecture contract", "",
                      "- Target: " + str(declared.get("arch")),
                      "- Architecture skill: " + str(declared.get("architecture_skill_status")),
                      "- Frozen workload: " + json.dumps(declared.get("workload"), ensure_ascii=False),
                      "- Validation: " + json.dumps(declared.get("validation"), ensure_ascii=False)])
        for skill in declared.get("skills", []):
            lines.append("- {}: {} (SHA256 {})".format(skill["role"], skill["path"], skill["sha256"]))
    methods = [(c, name, value) for c in report["comparisons"].values()
               for name, value in c.get("methods", {}).items()]
    if methods:
        lines.extend(["", "## Required metrics (each evaluated separately)", "",
                      "The summary ratio above is the primary metric; adoption requires all declared metrics.", "",
                      "| stage | metric | unit | reference median | candidate median | verdict | paired ratio | lower bound |",
                      "|---|---|---|---|---|---|---|---|"])
        for c, name, value in methods:
            cells = [c["stage"], name] + [value.get(k) for k in
                ("unit", "reference_median", "candidate_median", "verdict", "median_ratio", "lower_ratio_bound")]
            lines.append("| " + " | ".join(map(_cell, cells)) + " |")
        lines.extend(["", "Recommendation scope: frozen workload only. Whole-artifact adoption is not assessed by this run."])
    lines.extend(["", "Final relative to original: " + json.dumps(report["final_vs_original"], ensure_ascii=False),
                  "", "Final relative to normalized: not independently compared.",
                  "", "## Failures and unfinished work", ""])
    failures = report["failures"]
    lines.extend(["- " + _cell(item) for item in failures] if failures else ["None recorded."])
    lines.extend(["", "## Experiment hypotheses", "",
                  "| intent | direction | hypothesis | proposal outcome | actual payload moves | new findings |",
                  "|---|---|---|---|---|---|"])
    for row in report["ledger"]["rows"]:
        hypothesis = row.get("hypothesis", {})
        diagnostics = row.get("diagnostics", {})
        cells = [row.get("intent_id"), hypothesis.get("direction"), hypothesis.get("hypothesis"),
                 row["status"], len(diagnostics.get("actual_changes", {}).get("payload_moves", [])),
                 len(diagnostics.get("new_findings", []))]
        lines.append("| " + " | ".join(map(_cell, cells)) + " |")
    lines.extend(["", "## Scope", "", report["scope"], "",
                  "Screening score means the client's positive, higher-is-better EvalResult.tflops field.",
                  "Declared comparison metrics use their own unit and direction. Legacy score ratios are",
                  "time speedups only when the client score is throughput or inverse time. Statistical",
                  "assumptions and actual loaded code-object identity need target-hardware validation.", ""])
    if report["input_provenance"]:
        lines.extend(["Input provenance is an SDK sidecar, not the frozen manifest or loaded-code proof.", "",
                      "```json", json.dumps(report["input_provenance"], ensure_ascii=False, indent=2), "```", ""])
    if report["integrity_errors"]:
        lines.extend(["## Integrity errors", ""] + ["- " + _cell(e) for e in report["integrity_errors"]] + [""])
    return "\n".join(lines)


def snapshot_report(run_directory):
    """Read the current authoritative snapshot without exporting or measuring."""
    run = RunController(run_directory)
    return _snapshot_report(run, run.status())


def _snapshot_report(run, snapshot, output=None):
    directory = run.directory
    manifest, state = snapshot["manifest"], snapshot["state"]
    errors, candidates, verified = [], [], {}
    for candidate_id, candidate in state["candidates"].items():
        artifact = candidate["artifact"]
        integrity = "verified"
        try:
            verified[candidate_id] = _archive(directory, artifact)
        except (OSError, ValueError, KeyError) as exc:
            integrity = "invalid"
            errors.append("{}: {}".format(candidate_id, exc))
        batch = _latest_screen(state, candidate_id)
        measurement = (batch.get("measurement") or {}) if batch else {}
        score = measurement.get("tflops")
        candidates.append({"id": candidate_id, "parent_id": candidate.get("parent_id"),
                           "spec": candidate.get("spec"), "sha256": artifact["sha256"],
                           "archive_path": artifact["path"], "integrity": integrity,
                           "screen_status": batch["status"] if batch else "not_measured",
                           "screen_score": score if valid_score(score) else None,
                           "screen_batch_id": batch["id"] if batch else None})
    by_id = {c["id"]: c for c in candidates}

    def export(candidate_id, role):
        if candidate_id not in verified:
            return None
        item = dict(by_id[candidate_id])
        if output is None:
            return dict(item, export_path=None)
        destination = output / (role + ".s")
        _write(destination, verified[candidate_id])
        if hashlib.sha256(destination.read_bytes()).hexdigest() != item["sha256"]:
            destination.unlink()
            errors.append(role + ": exported SHA-256 mismatch")
            return None
        return dict(item, export_path=str(destination))

    screening = [c for c in candidates if c["integrity"] == "verified" and
                 c["screen_status"] == "measured" and valid_score(c["screen_score"])]
    best = max(screening, key=lambda c: c["screen_score"]) if screening else None
    screening_best = export(best["id"], "screening_best") if best else None
    comparisons = state.get("comparisons", {})
    incumbent = state.get("incumbent_id")
    evidence = comparisons.get(state.get("incumbent_evidence_id"), {})
    confirmed_best = None
    if incumbent:
        if (evidence.get("stage") == "confirm" and evidence.get("status") == "completed" and
                evidence.get("verdict") == "confirmed_gain" and evidence.get("candidate_id") == incumbent):
            confirmed_best = export(incumbent, "confirmed_best")
        else:
            errors.append("incumbent has no completed confirmed_gain evidence")
    final = state.get("final_result")
    selected, recommendation, final_vs_original = None, None, None
    if final:
        selected_id = final.get("selected_id")
        comparison = comparisons.get(final.get("comparison_id"), {})
        artifact = state["candidates"].get(selected_id, {}).get("artifact")
        consistent = (state.get("phase") == "finished" and artifact is not None and
                      artifact == final.get("selected_artifact"))
        if final.get("status") == "final_recommended":
            consistent = consistent and (manifest.get("comparison_policy") is not None and
                final.get("recommendation_id") == selected_id and selected_id == incumbent and
                confirmed_best is not None and comparison.get("stage") == "final" and
                comparison.get("status") == "completed" and comparison.get("verdict") == "confirmed_gain" and
                comparison.get("candidate_id") == selected_id and comparison.get("reference_id") == "original")
        elif final.get("status") == "original_retained":
            consistent = consistent and selected_id == "original" and final.get("recommendation_id") is None
        else:
            consistent = False
        if not consistent:
            errors.append("inconsistent final evidence; selected copy and recommendation withheld")
        elif not errors:
            selected = export(selected_id, "selected")
            if final["status"] == "final_recommended":
                recommendation = selected
        final_vs_original = comparison.get("analysis")
    failures = []
    for proposal in state["proposals"]:
        if proposal["status"] in ("rejected", "interrupted", "preparing", "import_requested",
                                  "import_rejected", "import_interrupted", "replay_requested",
                                  "replay_rejected", "replay_interrupted"):
            failures.append({"proposal_id": proposal["id"], "status": proposal["status"],
                             "error": proposal.get("error"), "error_code": proposal.get("error_code")})
    for batch in state["batches"].values():
        if batch["status"] != "measured":
            failures.append({"batch_id": batch["id"], "candidate_id": batch["candidate_id"],
                             "stage": batch.get("stage", "screen"), "status": batch["status"],
                             "error": (batch.get("measurement") or {}).get("error")})
    provenance = None
    if (directory / "input_provenance.json").exists():
        try:
            provenance = json.loads((directory / "input_provenance.json").read_text(encoding="utf-8"))
            _archive(directory, {"path": provenance["source"]["archive"], "sha256": provenance["source"]["sha256"]})
            if provenance["assembly_sha256"] != manifest["original_sha256"]:
                raise ValueError("provenance assembly does not match original")
            provenance["archive_integrity"] = "verified"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Sidecar failure is explicit but cannot rewrite the frozen run verdict.
            provenance = {"archive_integrity": "invalid", "error": str(exc)}
            errors.append("input provenance: " + str(exc))
    report = {"schema_version": 1, "run_id": manifest["run_id"], "run_dir": str(directory),
              "state_revision": state["revision"], "phase": state.get("phase", "legacy_read_only"),
              "environment_matches": snapshot["environment_matches"], "manifest": manifest,
              "search": snapshot["search"],
              "used": state["used"], "confirmation_status": state["confirmation_status"],
              "screening_best": screening_best, "confirmed_best": confirmed_best,
              "final_result": final, "selected": selected, "recommendation": recommendation,
              "final_vs_original": final_vs_original, "final_vs_normalized": None,
              "final_vs_original_methods": (final or {}).get("methods"),
              "candidates": candidates, "comparisons": comparisons,
              "batches": state["batches"], "attempts": state["attempts"], "proposals": state["proposals"],
              "ledger": ledger_snapshot(manifest, state),
              "failures": failures, "input_provenance": provenance, "integrity_errors": errors,
              "scope": "Snapshot of controller decisions on client-reported evidence; no new evaluation. "
                       "Reports do not provide shell isolation, semantic-equivalence proof, or hardware validation."}
    return report


def export_report(run_directory, out=None, json_path=None):
    run = RunController(run_directory)
    snapshot = run.status()  # controller lock, frozen manifest/schema validation
    directory = run.directory
    output = (Path(out) if out else directory / "report").resolve()
    destination = (Path(json_path) if json_path else output / "report.json").resolve()
    if destination.suffix not in (".json", ".jsonl"):
        raise ValueError("report JSON path must end in .json or .jsonl")
    for target in (output, destination):
        for ancestor in (target,) + tuple(target.parents):
            if (ancestor != directory and (ancestor / "manifest.json").is_file() and
                    (ancestor / "state.json").is_file()):
                raise ValueError("derived reports cannot write into another run")
        if (target == directory or directory in target.parents) and not (
                target == directory / "report" or directory / "report" in target.parents):
            raise ValueError("inside a run, derived reports must stay under RUN/report")
    markdown = destination.with_suffix(".md")
    output.mkdir(parents=True, exist_ok=True)
    # The dedicated export names always refer to this snapshot. Clear stale
    # derived copies before inspecting integrity; never leave a stale winner.
    for role in ("screening_best", "confirmed_best", "selected"):
        target = output / (role + ".s")
        if target.exists() or target.is_symlink():
            target.unlink()
    report = _snapshot_report(run, snapshot, output)
    errors = report["integrity_errors"]
    selected = report["selected"]
    _write(destination, (json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode())
    _write(markdown, render_markdown(report).encode())
    return {"json_path": str(destination), "markdown_path": str(markdown),
            "selected_path": selected["export_path"] if selected else None,
            "integrity_errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--out", help="derived-copy directory; default RUN/report")
    parser.add_argument("--json-path", help="JSON destination; .md written next to it")
    args = parser.parse_args(argv)
    try:
        result = export_report(args.run, args.out, args.json_path)
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result["integrity_errors"] else 0
    except (RunError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": {"code": getattr(exc, "code", "report_failed"), "message": str(exc)}}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
