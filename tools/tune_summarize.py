"""Summarise ONE tune run into client/<name>/tune_out/tune_result/.

Reads the authoritative per-eval results jsonl (written by agent_session.py
eval; see its --results-path) and emits, for that run:

  <stem>.summary.md    human-readable best/worst table (tflops, baseline, diff%)
  <stem>.summary.json  the same as structured data
  <stem>.screening_best_tf<TFLOPS>.s  highest-scoring screening candidate

"best"/"worst" are compatibility aliases for SCREENING scores, never independent
confirmation or a final recommendation. Legacy logs have no confirmation either.
``<stem>`` is the results filename without its .results.jsonl suffix, so
per-region runs (tune_prologue_epilogue.sh) never clobber each other.

Usage:
  python3.8 tools/tune_summarize.py --results <path/to/x.results.jsonl> \
            [--out client/<name>/tune_out/tune_result]

``--out`` defaults to ``tune_result/`` next to the results file's directory
(``<tune_out>/transcripts/x.results.jsonl`` -> ``<tune_out>/tune_result``).
"""
import json
import os
import shutil
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from harness.measurement import file_sha256, valid_score


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def _stem(results_path):
    base = os.path.basename(results_path)
    for suf in (".results.jsonl", ".jsonl"):
        if base.endswith(suf):
            return base[: -len(suf)]
    return os.path.splitext(base)[0]


def _load_rows(results_path):
    rows = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except ValueError:
                pass
    return rows


def _pct(impr):
    return "n/a" if impr is None else "{:+.2f}%".format(impr * 100)


def main(argv):
    results_path = _arg(argv, "--results")
    if not results_path or not os.path.exists(results_path):
        print("tune_summarize: --results <jsonl> is required and must exist",
              file=sys.stderr)
        return 2
    out_dir = _arg(argv, "--out", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(results_path))), "tune_result"))
    os.makedirs(out_dir, exist_ok=True)
    stem = _stem(results_path)

    rows = _load_rows(results_path)
    correct = [r for r in rows if r.get("correct") is True
               and r.get("compiled") is not False and valid_score(r.get("tflops"))
               and r.get("stage", "screen") == "screen"
               and r.get("verdict") not in (
                   "illegal", "baseline_failed", "compile_failed", "measurement_invalid")]

    summary = {"results": os.path.relpath(results_path, _REPO),
               "evals_total": len(rows), "evals_correct": len(correct),
               "schema_version": 2, "selection_kind": "screening",
               "confirmation_status": "not_performed",
               "confirmed_best": None, "recommendation": None,
               "screening_best": None, "screening_best_shader": None,
               "best": None, "worst": None, "best_shader": None,
               "archive_status": "not_available"}

    md = ["# tune result: {}".format(stem), "",
          "- source: `{}`".format(os.path.relpath(results_path, _REPO)),
          "- evals: {} total, {} valid screening results".format(len(rows), len(correct)),
          "- selection: highest screening score; independent confirmation not performed",
          "- final recommendation: none (legacy accepted is not confirmation)", ""]

    if not correct:
        md += ["**No correct eval was recorded for this run.**", ""]
        _write(out_dir, stem, summary, md, best_shader_src=None)
        print(json.dumps(summary, indent=2))
        return 0

    best = max(correct, key=lambda r: r["tflops"])
    worst = min(correct, key=lambda r: r["tflops"])

    def _entry(r):
        return {"round": r.get("round"), "region": r.get("region"),
                "tflops": r.get("tflops"), "baseline_tflops": r.get("baseline_tflops"),
                "improvement": r.get("improvement"), "accepted": r.get("accepted"),
                "note": r.get("note"), "layout": r.get("layout"),
                "shader": r.get("shader"), "artifact_sha256": r.get("artifact_sha256"),
                "stage": r.get("stage", "screen"), "verdict": r.get("verdict"),
                "baseline_kind": r.get("baseline_kind", "legacy_unspecified")}

    summary["best"] = _entry(best)
    summary["screening_best"] = summary["best"]
    summary["worst"] = _entry(worst)

    md += ["| kind | round | region | tflops | baseline | diff% | accepted |",
           "|---|---|---|---|---|---|---|"]
    for kind, r in (("screening best", best), ("screening worst", worst)):
        md.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            kind, r.get("round"), r.get("region"), r.get("tflops"),
            r.get("baseline_tflops"), _pct(r.get("improvement")), r.get("accepted")))
    md += ["",
           "best note: {}".format(best.get("note")),
           "worst note: {}".format(worst.get("note")), ""]

    # Preserve a screening candidate for later verification, not a recommendation.
    best_src = best.get("shader")
    best_dst = None
    if best_src and not os.path.isabs(best_src):
        best_src = os.path.join(_REPO, best_src)
    digest = best.get("artifact_sha256")
    if best_src and os.path.isfile(best_src) and digest and file_sha256(best_src) != digest:
        summary["archive_status"] = "digest_mismatch"
        md += ["screening candidate .s: archive digest mismatch; not copied", ""]
    elif best_src and os.path.isfile(best_src):
        tf = best.get("tflops")
        best_dst = os.path.join(out_dir, "{}.screening_best_tf{}.s".format(
            stem, ("%.3f" % tf) if tf is not None else "na"))
        shutil.copyfile(best_src, best_dst)
        summary["best_shader"] = os.path.relpath(best_dst, _REPO)
        summary["screening_best_shader"] = summary["best_shader"]
        summary["archive_status"] = "digest_verified" if digest else "legacy_no_digest"
        md += ["screening candidate .s: `{}` ({})".format(
            os.path.relpath(best_dst, _REPO), summary["archive_status"]), ""]
    else:
        md += ["screening candidate .s: (archive not found)", ""]

    _write(out_dir, stem, summary, md, best_shader_src=best_dst)
    print(json.dumps(summary, indent=2))
    return 0


def _write(out_dir, stem, summary, md_lines, best_shader_src=None):
    with open(os.path.join(out_dir, stem + ".summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(out_dir, stem + ".summary.md"), "w") as f:
        f.write("\n".join(md_lines) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
