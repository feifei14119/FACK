"""Read compatible run archives as unmeasured, reconstructible warm starts.

Historical measurements establish provenance and ordering only. They are never
returned as samples to install in a new run, and cannot promote its incumbent.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
from pathlib import Path
import statistics

from agent.replay import ReplayError, _spec, source_sha256, verify_chain
from harness.comparison import assess_pairs, look_sizes, pair_order, validate_policy
from harness.validation import evidence as validation_evidence, assess_methods, combined_verdict
from harness.measurement import valid_score


class HistoryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _require(condition, message, code="invalid_history"):
    if not condition:
        raise HistoryError(code, message)


def _compatibility(manifest, state, current):
    # Imported lazily so RunController may use this module without a circular
    # import. Future schemas need the current controller's explicit support.
    from agent.run import SCHEMA_VERSION
    fields = ("schema_version", "original_sha256", "engine_identity", "runtime_identity",
              "evaluation_contract", "build_policy", "default_region")
    # There is no best-effort fallback for missing contract fields.
    for key in fields:
        _require(key in manifest and key in current and manifest[key] is not None and
                 current[key] is not None and manifest[key] == current[key],
                 "history/current identity mismatch: " + key, "history_mismatch")
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == SCHEMA_VERSION and
             state.get("schema_version") == manifest["schema_version"], "unsupported history schema")
    _require(state.get("manifest_sha256") == _digest(manifest), "frozen history manifest digest mismatch")


def _artifacts(directory, manifest, state):
    candidates = state.get("candidates")
    _require(isinstance(candidates, dict) and "original" in candidates, "missing candidate archive")
    sources = {}
    for candidate_id, candidate in candidates.items():
        _require(isinstance(candidate, dict) and candidate.get("id") == candidate_id,
                 "candidate identity mismatch")
        artifact = candidate.get("artifact", {})
        _require(isinstance(artifact.get("path"), str), "missing candidate path")
        path = (directory / artifact["path"]).resolve()
        _require(directory in path.parents and path.is_file(), "candidate path is missing or outside the run")
        data = path.read_bytes()
        _require(hashlib.sha256(data).hexdigest() == artifact.get("sha256") and
                 type(artifact.get("size_bytes")) is int and len(data) == artifact["size_bytes"],
                 "candidate artifact digest or size mismatch")
        sources[candidate_id] = data.decode("utf-8")
    original = candidates["original"]
    _require(original.get("parent_id") is None and original.get("spec") is None and
             source_sha256(sources["original"]) == manifest["original_sha256"], "original provenance mismatch")
    return sources


def _batch(state, batch_id, candidate_id, stage, count, context=None, validation=None):
    batch = state["batches"].get(batch_id)
    _require(isinstance(batch, dict) and batch.get("id") == batch_id and
             batch.get("candidate_id") == candidate_id and batch.get("stage") == stage and
             batch.get("status") == "measured", "missing successful historical batch")
    measurement = batch.get("measurement") or {}
    ids, samples = batch.get("attempt_ids", []), measurement.get("samples", [])
    _require(measurement.get("status") == "measured" and measurement.get("correct") is True and
             len(ids) == count and len(set(ids)) == count and len(samples) == count,
             "incomplete historical measurement")
    digest = state["candidates"][candidate_id]["artifact"]["sha256"]
    scores = []
    for attempt_id, sample in zip(ids, samples):
        attempt = state["attempts"].get(attempt_id) or {}
        result = attempt.get("result") or {}
        _require(attempt.get("id") == attempt_id and attempt.get("batch_id") == batch_id and
                 attempt.get("candidate_id") == candidate_id and attempt.get("stage") == stage and
                 attempt.get("status") == "returned" and attempt.get("source_sha256") == digest and
                 sample.get("source_sha256") == digest and sample.get("result") == result,
                 "measurement attempt/source linkage mismatch")
        for key, value in (context or {}).items():
            _require(batch.get(key) == value and attempt.get(key) == value,
                     "paired measurement context mismatch")
        _require(result.get("compiled") is True and result.get("correct") is True and
                 valid_score(result.get("tflops")), "invalid historical sample")
        if validation:
            validation_evidence(result, validation)
        scores.append(result["tflops"])
    score = statistics.median(scores)
    _require(measurement.get("tflops") == score, "historical batch summary mismatch")
    return score, ids


def _screen(manifest, state, candidate_id):
    batches = [b for b in state["batches"].values()
               if b.get("candidate_id") == candidate_id and b.get("stage") == "screen"]
    _require(bool(batches), "historical original/candidate screening evidence is missing")
    batch = max(batches, key=lambda b: b["sequence"])
    _batch(state, batch["id"], candidate_id, "screen", manifest["perf_repeats"],
           validation=manifest["evaluation_contract"].get("agent_profile", {}).get("validation"))


def _comparison(manifest, state, comparison):
    _require(isinstance(comparison, dict) and comparison.get("stage") in ("confirm", "final") and
             comparison.get("status") == "completed" and comparison.get("verdict") == "confirmed_gain",
             "historical winner lacks completed confirmation")
    stage, policy = comparison["stage"], validate_policy(manifest["comparison_policy"])
    validation = manifest["evaluation_contract"].get("agent_profile", {}).get("validation")
    for role in ("candidate", "reference"):
        candidate = state["candidates"].get(comparison.get(role + "_id"))
        _require(candidate is not None and candidate["artifact"]["sha256"] == comparison.get(role + "_sha256"),
                 "historical comparison source mismatch")
        _screen(manifest, state, candidate["id"])
    _require(comparison["candidate_sha256"] != comparison["reference_sha256"], "identical historical A/B artifacts")
    pairs = comparison.get("pairs", [])
    _require(len(pairs) in look_sizes(policy, stage), "historical comparison is incomplete")
    scores, used = [], set()
    for index, pair in enumerate(pairs):
        _require(pair.get("index") == index and pair.get("order") == list(pair_order(index)),
                 "historical pair ordering mismatch")
        actual = {}
        for role in pair_order(index):
            score, ids = _batch(state, pair.get("batches", {}).get(role), comparison[role + "_id"], stage, 1,
                                {"comparison_id": comparison["id"], "pair_index": index, "role": role}, validation)
            if validation:
                values, normalized = validation_evidence(state["attempts"][ids[0]]["result"], validation)
                _require(pair.get("metric_values", {}).get(role) == values and
                         pair.get("metric_scores", {}).get(role) == normalized,
                         "historical client metrics mismatch")
                score = normalized[validation["primary_metric"]]
            _require(not used.intersection(ids), "historical comparison reuses a sample")
            used.update(ids)
            actual[role] = score
        _require(actual == pair.get("scores"), "historical pair score mismatch")
        scores.append(actual)
    try:
        analysis = assess_pairs(scores, policy, stage)
    except ValueError:
        analysis = None
    _require(analysis is not None, "historical comparison did not stop at its first stopping look")
    _require(analysis == comparison.get("analysis") and analysis["verdict"] == "confirmed_gain",
             "historical confirmation does not reproduce")
    if validation:
        methods = assess_methods(pairs, validation, policy, stage)
        _require(methods == comparison.get("methods") and combined_verdict(methods) == "confirmed_gain",
                 "historical client metric confirmation does not reproduce")


def _reference_chain(manifest, state, sources, comparison, seen=None):
    """A comparison against an incumbent must lead back to original evidence."""
    seen = set() if seen is None else set(seen)
    evidence_id = comparison.get("id")
    _require(evidence_id not in seen, "cycle in historical reference evidence")
    seen.add(evidence_id)
    _comparison(manifest, state, comparison)
    reference_id = comparison["reference_id"]
    if reference_id == "original":
        return
    chain = candidate_chain(state, reference_id, manifest["build_policy"])
    rebuilt = verify_chain(sources["original"], chain, manifest["build_policy"])
    _require(rebuilt["source"] == sources[reference_id], "reference ancestry does not reproduce")
    previous = [c for c in state["comparisons"].values()
                if c.get("candidate_id") == reference_id and c.get("stage") == "confirm" and
                c.get("status") == "completed" and c.get("verdict") == "confirmed_gain" and
                isinstance(c.get("finished_at"), (int, float)) and
                c["finished_at"] <= comparison.get("started_at", -1)]
    _require(bool(previous), "historical reference has no prior confirmation against original ancestry")
    _reference_chain(manifest, state, sources, previous[-1], seen)


def candidate_chain(state, candidate_id, build_policy):
    """Extract an ancestry recipe; archive verification is the caller's job.

    Useful to controllers composing candidates already protected by their own
    run lock and digest checks. This function alone does not trust or import a
    candidate: callers must pass its output through ``verify_chain``.
    """
    chain, seen = [], set()
    while candidate_id != "original":
        _require(candidate_id not in seen, "cycle in historical candidate ancestry")
        seen.add(candidate_id)
        candidate = state["candidates"].get(candidate_id)
        _require(candidate is not None and candidate.get("static_ok") is True, "missing statically valid ancestor")
        parent = state["candidates"].get(candidate.get("parent_id"))
        _require(parent is not None, "missing historical parent")
        spec = candidate.get("spec")
        _require(isinstance(spec, dict), "history artifact has no constrained build recipe")
        if candidate_id == "normalized":
            _require(parent["id"] == "original" and spec.get("kind") == "ladder", "invalid normalization ancestry")
        else:
            _require(spec.get("kind") in ("layout", "order"), "arbitrary assembly import is not a replayable intent")
            matched = False
            for proposal in state["proposals"]:
                if (proposal.get("candidate_id") != candidate_id or proposal.get("parent_id") != parent["id"] or
                        proposal.get("status") not in ("prepared", "duplicate", "no_change")):
                    continue
                obs = state["observations"].get(proposal.get("observation_id"), {})
                digest = parent["artifact"]["sha256"]
                report = proposal.get("report") or {}
                if (obs.get("parent_id") != parent["id"] or obs.get("base_sha256") != digest or
                        obs.get("observation_id") != proposal.get("observation_id") or
                        proposal.get("base_sha256") != digest or report.get("legal") is not True or report.get("skipped")):
                    continue
                proposed = dict(proposal["spec"])
                proposed.setdefault("region", obs.get("region"))
                if proposed["region"] != obs.get("region"):
                    continue
                if _spec(proposed, build_policy) == _spec(spec, build_policy):
                    matched = True
                    break
            _require(matched, "candidate lacks version-bound successful proposal evidence")
        chain.append({"spec": copy.deepcopy(spec), "source_sha256": parent["artifact"]["sha256"],
                      "candidate_sha256": candidate["artifact"]["sha256"]})
        candidate_id = parent["id"]
    return list(reversed(chain))


def load_history(directory, current_manifest, candidate_id=None):
    """Validate a complete compatible run and return one unmeasured recipe.

    Default selection is the final recommendation, or the confirmed incumbent
    of a run that has not finalized. A failed final is not silently replaced
    by its former screening/confirmation winner. All archive artifacts are
    checked; the chosen chain and its reference measurements are reconstructed.
    """
    directory = Path(directory).resolve()
    try:
        with open(directory / ".lock", "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise HistoryError("history_busy", "history run is being modified") from None
            with open(directory / "manifest.json", encoding="utf-8") as stream:
                manifest = json.load(stream)
            with open(directory / "state.json", encoding="utf-8") as stream:
                state = json.load(stream)
            _compatibility(manifest, state, current_manifest)
            sources = _artifacts(directory, manifest, state)
            _require(all(isinstance(state.get(k), dict) for k in ("batches", "attempts", "comparisons", "observations")) and
                     isinstance(state.get("proposals"), list), "incomplete historical state")
            _require(not any(x.get("status") in ("running", "preparing")
                             for key in ("batches", "attempts", "comparisons") for x in state[key].values()) and
                     not any(x.get("status") in ("preparing", "import_requested", "replay_requested")
                             for x in state["proposals"]) and
                     not any(x.get("status") == "running" for x in state.get("imports", [])),
                     "history contains unfinished work; recover it first")
            final = state.get("final_result")
            if final is not None:
                _require(final.get("status") == "final_recommended", "history retained original; no historical winner", "no_history_candidate")
                selected = final.get("selected_id")
                _require(candidate_id in (None, selected), "candidate was not the final recommendation", "no_history_candidate")
                evidence_id = final.get("comparison_id")
            else:
                selected = candidate_id or state.get("incumbent_id")
                evidence_id = state.get("incumbent_evidence_id") if selected == state.get("incumbent_id") else None
                if evidence_id is None:
                    evidence = [c for c in state["comparisons"].values() if c.get("candidate_id") == selected and
                                c.get("stage") == "confirm" and c.get("verdict") == "confirmed_gain"]
                    evidence_id = evidence[-1]["id"] if evidence else None
            _require(selected in state["candidates"] and selected != "original" and evidence_id in state["comparisons"],
                     "history has no confirmed candidate", "no_history_candidate")
            evidence = state["comparisons"][evidence_id]
            _require(evidence.get("id") == evidence_id and evidence.get("candidate_id") == selected,
                     "historical winner evidence identity mismatch")
            if final is not None:
                _require(evidence.get("stage") == "final" and evidence.get("reference_id") == "original" and
                         state.get("phase") == "finished" and final.get("recommendation_id") == selected and
                         final.get("fallback_id") is None and
                         final.get("selected_artifact") == state["candidates"][selected]["artifact"],
                         "final recommendation evidence mismatch")
            else:
                _require(evidence.get("stage") == "confirm", "incumbent evidence is not a confirmation")
            _screen(manifest, state, "original")
            _reference_chain(manifest, state, sources, evidence)
            chain = candidate_chain(state, selected, manifest["build_policy"])
            rebuilt = verify_chain(sources["original"], chain, manifest["build_policy"])
            _require(rebuilt["source"] == sources[selected], "history recipe does not reproduce candidate archive")
            return {"history_run_dir": str(directory), "history_run_id": manifest.get("run_id"),
                    "manifest_sha256": state["manifest_sha256"], "state_sha256": _digest(state),
                    "original_sha256": manifest["original_sha256"], "candidate_id": selected,
                    "candidate_sha256": rebuilt["sha256"], "chain": chain,
                    "evidence_ref": {"comparison_id": evidence_id, "stage": evidence["stage"]},
                    "requires_evaluation": True, "measurements_imported": False}
    except HistoryError:
        raise
    except ReplayError as exc:
        raise HistoryError(exc.code, str(exc)) from exc
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HistoryError("invalid_history", "incomplete or malformed history: " + str(exc)) from exc
