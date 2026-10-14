"""Persistent control of single-kernel screening and optional paired validation.

Only a frozen comparison policy can promote an incumbent. state.json is the
single transactional authority, including budgets, attempts and final results.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager

from agent.artifacts import save_assembly
from agent.diagnostics import diagnose_candidate
from agent.directions import validate_search_policy
from agent.search_control import (SearchControllerMixin, search_status, check_search_open,
                                  check_navigation_budget, guidance, check_reuse_proposal, charge_reuse_proposal,
                                  check_comparison_navigation)
from agent.replay_controller import ReplayControllerMixin
from agent.history_controller import HistoryControllerMixin
from agent.ledger import hypothesis_record, ledger_snapshot, validate_refs
from agent.session import AgentSession
from harness.comparison import (SEQUENTIAL_METHOD, assess_look, assess_pairs, look_sizes,
                                pair_order, planned_pairs, validate_policy)
from harness.measurement import file_sha256, measure_screen, snapshot_result
from search import driver

REPO = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 2


class RunError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def engine_identity():
    """Fingerprint local engine code and its checked-in model inputs."""
    files = []
    for directory in ("agent", "reorder", "isa", "search", "harness"):
        files.extend((REPO / directory).rglob("*.py"))
    files.extend((REPO / "client").glob("*.py"))
    files.append(REPO / "tools/tune_run.py")
    return _digest([(os.path.relpath(str(p), str(REPO)), file_sha256(str(p)))
                    for p in sorted(set(files)) if p.is_file()])


def runtime_identity():
    # Deliberate allowlist: do not persist credentials or the entire environment.
    names = ("ROCM_PATH", "ROCM_LLVM_BIN", "ROCM_SDK_CORE", "ROCM_SDK_DEVEL")
    return {"python": sys.version, "executable": sys.executable,
            "settings": {k: os.environ.get(k) for k in names}}


def _atomic_json(path, value):
    path = Path(path)
    data = _canonical(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=".state-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
        directory_fd = os.open(str(path.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RunController(SearchControllerMixin, ReplayControllerMixin, HistoryControllerMixin):
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        if not (self.directory / "manifest.json").is_file():
            raise RunError("invalid_run", "run manifest is missing")

    @classmethod
    def create(cls, directory, seed_src, evaluation_contract, *, eval_call_limit=24,
               proposal_limit=64, perf_repeats=3, final_eval_reserve=0,
               wall_time_limit=None, region="loop", protect_prefetch=True,
               comparison_policy=None, search_policy=None):
        for name, value, minimum in (("eval_call_limit", eval_call_limit, 1),
                                      ("proposal_limit", proposal_limit, 1),
                                      ("perf_repeats", perf_repeats, 1),
                                      ("final_eval_reserve", final_eval_reserve, 0)):
            if type(value) is not int or value < minimum:
                raise ValueError("invalid " + name)
        if final_eval_reserve > eval_call_limit:
            raise ValueError("final reserve exceeds total evaluation budget")
        if wall_time_limit is not None and (isinstance(wall_time_limit, bool) or
                not isinstance(wall_time_limit, (int, float)) or
                not math.isfinite(wall_time_limit) or wall_time_limit <= 0):
            raise ValueError("wall_time_limit must be a finite positive duration")
        if not isinstance(evaluation_contract, dict):
            raise ValueError("evaluation_contract must be an object")
        contract = json.loads(_canonical(evaluation_contract))
        comparison = (validate_policy(json.loads(_canonical(comparison_policy)))
                      if comparison_policy is not None else None)
        if comparison is not None and final_eval_reserve < 2 * planned_pairs(comparison, "final"):
            raise ValueError("final reserve must cover both sides of the complete final comparison")
        search_policy = validate_search_policy(search_policy)
        if search_policy["independent_eval_reserve"] > eval_call_limit - final_eval_reserve:
            raise ValueError("independent reserve exceeds the non-final evaluation budget")
        policy = {"opt_level": 1, "protect_prefetch": bool(protect_prefetch),
                  "strict_verify": False}
        normalized_spec = dict(policy, kind="ladder", level=1, region=region)
        normalized, ok = driver.build_candidate(seed_src, normalized_spec)
        diagnostics = diagnose_candidate(seed_src, seed_src, normalized, spec=normalized_spec)
        ok = ok and diagnostics["ok_vs_original"]
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=False)
        manifest = {"schema_version": SCHEMA_VERSION, "run_id": directory.name,
                    "created_at": time.time(), "engine_identity": engine_identity(),
                    "runtime_identity": runtime_identity(), "evaluation_contract": contract,
                    "default_region": region, "build_policy": policy,
                    "budget": {"eval_call_limit": eval_call_limit,
                               "proposal_limit": proposal_limit,
                               "final_eval_reserve": final_eval_reserve,
                               "wall_time_limit": wall_time_limit},
                    "perf_repeats": perf_repeats, "comparison_policy": comparison, "search_policy": search_policy}
        candidates = {}
        for name, text, spec, static_ok in (("original", seed_src, None, None),
                                           ("normalized", normalized, normalized_spec, ok)):
            artifact = save_assembly(text, str(directory))
            artifact["path"] = os.path.relpath(artifact["path"], str(directory))
            candidates[name] = {"id": name, "artifact": artifact, "spec": spec,
                                "static_ok": static_ok, "parent_id": None if name == "original" else "original"}
        candidates["normalized"]["diagnostics"] = diagnostics
        manifest["original_sha256"] = candidates["original"]["artifact"]["sha256"]
        state = {"schema_version": SCHEMA_VERSION, "manifest_sha256": _digest(manifest),
                 "revision": 0, "parent_revision": 0, "exploration_parent_id": "original",
                 "incumbent_id": None, "confirmation_status": "not_performed",
                 "used": {"proposals": 0, "eval_calls": 0}, "candidates": candidates,
                 "observations": {}, "proposals": [], "batches": {}, "attempts": {},
                 "comparisons": {}, "confirmation_count": 0, "incumbent_evidence_id": None,
                 "phase": "search", "final_result": None}
        _atomic_json(directory / "manifest.json", manifest)
        _atomic_json(directory / "state.json", state)
        return cls(directory)

    @contextmanager
    def _locked(self):
        with open(self.directory / ".lock", "a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RunError("run_busy", "another process is using this run") from None
            try:
                with open(self.directory / "manifest.json", encoding="utf-8") as f:
                    manifest = json.load(f)
                with open(self.directory / "state.json", encoding="utf-8") as f:
                    state = json.load(f)
                if (manifest.get("schema_version") not in (1, SCHEMA_VERSION) or
                        state.get("schema_version") != manifest.get("schema_version") or
                        state.get("manifest_sha256") != _digest(manifest)):
                    raise RunError("manifest_mismatch", "run schema or frozen manifest changed")
                yield manifest, state
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _save(self, state):
        state["revision"] += 1
        _atomic_json(self.directory / "state.json", state)

    def _check_identity(self, manifest):
        if manifest["schema_version"] != SCHEMA_VERSION:
            raise RunError("schema_upgrade_required", "old runs are read-only; start a new run with the current schema")
        if (manifest["engine_identity"] != engine_identity() or
                manifest["runtime_identity"] != runtime_identity()):
            raise RunError("environment_changed", "engine or recorded runtime settings changed; start a new run")

    def _check_deadline(self, manifest):
        limit = manifest["budget"]["wall_time_limit"]
        if limit is not None and time.time() >= manifest["created_at"] + limit:
            raise RunError("wall_time_exhausted", "run deadline reached; no new client call may start")

    @staticmethod
    def _check_pending(state, active_import_id=None, active_replay_request_id=None):
        if (any(b["status"] == "running" for b in state["batches"].values()) or
                any(c["status"] == "running" for c in state["comparisons"].values()) or
                any(p["status"] == "preparing" or
                    (p["status"] == "replay_requested" and p["id"] != active_replay_request_id) or
                    (p["status"] == "import_requested" and
                     (active_import_id is None or p.get("provenance", {}).get("import_id") != active_import_id))
                    for p in state["proposals"]) or
                any(action["status"] == "running" and action["id"] != active_import_id
                    for action in state.get("imports", []))):
            raise RunError("recovery_required", "unfinished comparison, batch or proposal; run resume before continuing")

    def _ready(self, manifest, state):
        self._check_identity(manifest)
        self._check_pending(state, getattr(self, "_active_history_import_id", None),
                            getattr(self, "_active_replay_request_id", None))
        if state["phase"] != "search":
            raise RunError("run_closed", "final has closed this run; start a new run to explore further")

    def _source(self, state, candidate_id):
        candidate = state["candidates"].get(candidate_id)
        if candidate is None:
            raise RunError("unknown_candidate", "unknown candidate: " + candidate_id)
        artifact = candidate["artifact"]
        path = (self.directory / artifact["path"]).resolve()
        if self.directory not in path.parents or not path.is_file():
            raise RunError("artifact_invalid", "candidate archive is missing or outside the run")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            raise RunError("artifact_invalid", "candidate archive digest mismatch")
        return data.decode("utf-8")

    def status(self):
        with self._locked() as (manifest, state):
            return {"run_dir": str(self.directory), "manifest": manifest, "state": state,
                    "search": search_status(manifest, state),
                    "environment_matches": (manifest["engine_identity"] == engine_identity() and
                                            manifest["runtime_identity"] == runtime_identity())}

    def source(self, candidate_id):
        """Read a digest-verified archive (also useful for client initialization)."""
        with self._locked() as (_, state):
            return self._source(state, candidate_id)

    def observe(self, region=None):
        with self._locked() as (manifest, state):
            return self._observe(manifest, state, region)

    def _observe(self, manifest, state, region=None, *, parent_id=None):
        self._ready(manifest, state)
        region = region or manifest["default_region"]
        parent = parent_id or state["exploration_parent_id"]
        source = self._source(state, parent)
        session = AgentSession(source, None, region=region, out_store=str(self.directory),
                               protect_prefetch=manifest["build_policy"]["protect_prefetch"])
        facts = session.observe(with_direction=False).to_dict()
        identity = {"observation_id": uuid.uuid4().hex, "parent_id": parent,
                    "base_sha256": state["candidates"][parent]["artifact"]["sha256"],
                    "parent_revision": state["parent_revision"], "region": region}
        state["observations"][identity["observation_id"]] = dict(identity, facts=facts)
        self._save(state)
        return dict(facts=facts, **identity)

    def prepare(self, observation_id, base_sha256, spec, *, hypothesis=None):
        with self._locked() as (manifest, state):
            return self._prepare(manifest, state, observation_id, base_sha256, spec, hypothesis=hypothesis)

    def _prepare(self, manifest, state, observation_id, base_sha256, spec, *, hypothesis=None, detached=False, provenance=None):
        self._ready(manifest, state)
        self._check_deadline(manifest)
        check_search_open(manifest, state)
        if state["used"]["proposals"] >= manifest["budget"]["proposal_limit"]:
            raise RunError("proposal_budget_exhausted", "proposal budget exhausted")
        obs_parent = state["observations"].get(observation_id, {}).get("parent_id")
        reuse = (bool(state["candidates"].get(obs_parent, {}).get("reuse")) or
                 isinstance(hypothesis, dict) and hypothesis.get("source") in ("knowledge", "history"))
        if reuse:
            check_reuse_proposal(manifest, state)
        # Freeze an independently serializable request before using it.
        spec = json.loads(_canonical(spec))
        proposal = {"id": uuid.uuid4().hex, "observation_id": observation_id,
                    "base_sha256": base_sha256, "spec": spec, "status": "preparing",
                    "reuse": bool(reuse), "reuse_charged": bool(reuse), "detached": bool(detached),
                    "provenance": json.loads(_canonical(provenance)) if provenance is not None else None}
        state["used"]["proposals"] += 1
        state["proposals"].append(proposal)
        self._save(state)
        try:
            proposal["hypothesis"] = hypothesis_record(hypothesis, state)
            obs = state["observations"].get(observation_id)
            if (obs is None or obs["base_sha256"] != base_sha256 or
                    (not detached and obs["parent_id"] != state["exploration_parent_id"]) or
                    obs["parent_revision"] != state["parent_revision"]):
                raise RunError("stale_observation", "observe the current parent before proposing instruction IDs")
            if not isinstance(spec, dict) or spec.get("kind") not in ("layout", "order"):
                raise RunError("invalid_spec", "run mode currently accepts layout or order specs")
            allowed = {"kind", "region", "layout" if spec["kind"] == "layout" else "order"}
            if set(spec) - allowed or spec.get("region", obs["region"]) != obs["region"]:
                raise RunError("invalid_spec", "spec changes the observation region or frozen build policy")
            value = spec.get(spec["kind"])
            if spec["kind"] == "layout":
                if (not isinstance(value, dict) or
                        any(not re.fullmatch(r"0|[1-9][0-9]*", k) for k in value)):
                    raise RunError("invalid_spec", "layout slots must be canonical nonnegative integers")
                sequences = list(value.values())
            else:
                sequences = [value]
            if any(not isinstance(ids, list) or
                   any(type(i) is not int or i < 0 for i in ids) for ids in sequences):
                raise RunError("invalid_spec", "instruction IDs must be lists of nonnegative integers")
            ids = [i for seq in sequences for i in seq]
            if len(set(ids)) != len(ids):
                raise RunError("invalid_spec", "duplicate instruction IDs")
            parent = obs["parent_id"]
            proposal["parent_id"] = parent
            proposal["intent_id"] = _digest({"base_sha256": base_sha256, "spec": dict(spec, region=obs["region"]),
                                              "region": obs["region"], "build_policy": manifest["build_policy"],
                                              "evaluation_contract": manifest["evaluation_contract"]})
            source = self._source(state, parent)
            session = AgentSession(source, None, region=obs["region"], out_store=str(self.directory),
                                   protect_prefetch=manifest["build_policy"]["protect_prefetch"])
            if spec["kind"] == "layout":
                layout = {int(k): list(v) for k, v in spec["layout"].items()}
                report = session.propose([layout])[0]
                report = {"legal": report.legal, "placed": report.placed, "skipped": report.skipped}
                spec["layout"] = layout
            else:
                report = session.propose_orders([spec["order"]])[0]
            proposal["report"] = report
            if not report["legal"] or report.get("skipped"):
                raise RunError("proposal_rejected", "proposal has illegal or skipped placements; revise it")
            build_spec = dict(spec, region=obs["region"], **manifest["build_policy"])
            text, ok = driver.build_candidate(source, build_spec)
            diagnostics = diagnose_candidate(self._source(state, "original"), source, text,
                                             spec=build_spec, strict_verify=manifest["build_policy"]["strict_verify"])
            proposal["diagnostics"] = diagnostics
            if not ok or not diagnostics["ok_vs_original"]:
                raise RunError("verify_failed", "materialized candidate failed static verification")
            artifact = save_assembly(text, str(self.directory))
            artifact["path"] = os.path.relpath(artifact["path"], str(self.directory))
            matches = [c["id"] for c in state["candidates"].values()
                       if c["artifact"]["sha256"] == artifact["sha256"]]
            candidate_id = matches[0] if matches else "cand_" + artifact["sha256"]
            if not matches:
                state["candidates"][candidate_id] = {
                    "id": candidate_id, "artifact": artifact, "parent_id": parent,
                    "spec": build_spec, "static_ok": True, "diagnostics": diagnostics,
                    "direction": proposal["hypothesis"]["direction"], "reuse": bool(reuse)}
            if candidate_id != "original":
                candidate = state["candidates"][candidate_id]
                if candidate.get("reuse") and not proposal["reuse_charged"]:
                    charge_reuse_proposal(manifest, state, proposal)
                candidate["reuse"] = bool(candidate.get("reuse") or proposal["reuse"])
            proposal.update(candidate_id=candidate_id, parent_id=parent,
                            status="no_change" if artifact["sha256"] == base_sha256 else
                                   "duplicate" if matches else "prepared")
            self._save(state)
            return copy.deepcopy(proposal)
        except Exception as exc:
            code = exc.code if isinstance(exc, RunError) else "prepare_failed"
            proposal.update(status="rejected", error_code=code, error=str(exc))
            self._save(state)
            raise RunError(code, str(exc)) from exc

    def _charge_history_request(self, manifest, state, action):
        self._ready(manifest, state)
        self._check_deadline(manifest)
        check_search_open(manifest, state)
        if state["used"]["proposals"] >= manifest["budget"]["proposal_limit"]:
            raise RunError("proposal_budget_exhausted", "proposal budget exhausted")
        check_reuse_proposal(manifest, state)
        proposal = {"id": uuid.uuid4().hex, "status": "import_requested",
                    "spec": {"kind": "history_request"}, "parent_id": state["exploration_parent_id"],
                    "base_sha256": state["candidates"][state["exploration_parent_id"]]["artifact"]["sha256"],
                    "reuse": True, "reuse_charged": True,
                    "provenance": {"import_id": action["id"], "history_run_dir": action["history_run_dir"]},
                    "hypothesis": hypothesis_record({"source": "history", "direction": "history_warm_start"}, state)}
        state["used"]["proposals"] += 1
        state["proposals"].append(proposal)
        self._save(state)
        return proposal

    def _charge_import_normalized(self, manifest, state, provenance):
        """Import the already-built normalization as a charged history step."""
        self._ready(manifest, state)
        self._check_deadline(manifest)
        check_search_open(manifest, state)
        if state["used"]["proposals"] >= manifest["budget"]["proposal_limit"]:
            raise RunError("proposal_budget_exhausted", "proposal budget exhausted")
        check_reuse_proposal(manifest, state)
        candidate = state["candidates"]["normalized"]
        self._source(state, "normalized")
        if candidate["static_ok"] is not True:
            raise RunError("verify_failed", "normalized failed the fixed original static gate")
        obs = self._observe(manifest, state, manifest["default_region"], parent_id="original")
        proposal = {"id": uuid.uuid4().hex, "observation_id": obs["observation_id"],
                    "base_sha256": manifest["original_sha256"], "parent_id": "original",
                    "candidate_id": "normalized", "spec": copy.deepcopy(candidate["spec"]),
                    "status": "duplicate", "reuse": True, "reuse_charged": True,
                    "provenance": copy.deepcopy(provenance),
                    "hypothesis": hypothesis_record({"source": "history", "direction": "history_warm_start"}, state),
                    "diagnostics": copy.deepcopy(candidate.get("diagnostics"))}
        state["used"]["proposals"] += 1
        state["proposals"].append(proposal)
        candidate["reuse"] = True
        self._save(state)
        return copy.deepcopy(proposal)

    def ledger(self):
        with self._locked() as (manifest, state):
            return ledger_snapshot(manifest, state)

    def annotate(self, text, evidence_refs):
        with self._locked() as (manifest, state):
            self._check_identity(manifest)
            self._check_pending(state)
            if not isinstance(text, str) or not 1 <= len(text) <= 4000:
                raise RunError("invalid_annotation", "annotation must be a nonempty bounded string")
            annotation = {"id": uuid.uuid4().hex, "text": text,
                          "evidence_refs": validate_refs(evidence_refs, state),
                          "authority": "agent_interpretation_only"}
            state.setdefault("annotations", []).append(annotation)
            self._save(state)
            return copy.deepcopy(annotation)

    @staticmethod
    def _latest_batch(state, candidate_id):
        batches = [b for b in state["batches"].values()
                   if b["candidate_id"] == candidate_id and b["stage"] == "screen"]
        return max(batches, key=lambda b: b["sequence"]) if batches else None

    def evaluate(self, candidate_id, evaluator, *, repeat=False, evaluation_contract=None):
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            if evaluation_contract is not None and evaluation_contract != manifest["evaluation_contract"]:
                raise RunError("contract_mismatch", "client evaluation contract changed")
            self._source(state, candidate_id)
            candidate = state["candidates"][candidate_id]
            if candidate["static_ok"] is False:
                raise RunError("verify_failed", "candidate failed static verification")
            if candidate_id != "original":
                baseline = self._latest_batch(state, "original")
                if baseline is None or baseline["status"] != "measured":
                    raise RunError("baseline_required", "original must pass screening before evaluating candidates")
            previous = self._latest_batch(state, candidate_id)
            if previous is not None and not repeat:
                if previous["status"] == "interrupted":
                    raise RunError("repeat_required", "interrupted batch requires an explicit charged repeat")
                return dict(copy.deepcopy(previous), cached=True)
            check_search_open(manifest, state)
            self._check_deadline(manifest)
            repeats = manifest["perf_repeats"]
            self._check_eval_budget(manifest, state, repeats, "screen")
            check_navigation_budget(manifest, state, candidate_id, repeats, "screen")
            batch = self._measure(manifest, state, candidate_id, evaluator, repeats, "screen")
            return dict(batch, cached=False)

    @staticmethod
    def _check_eval_budget(manifest, state, count, stage):
        budget = manifest["budget"]
        ceiling = budget["eval_call_limit"]
        if stage != "final":
            ceiling -= budget["final_eval_reserve"]
        if state["used"]["eval_calls"] + count > ceiling:
            raise RunError("eval_budget_exhausted", "insufficient budget for the complete operation; final reserve is protected")

    def _measure(self, manifest, state, candidate_id, evaluator, repeats, stage, context=None):
        """Caller holds the run lock and prechecks the whole operation's budget."""
        source = self._source(state, candidate_id)
        candidate = state["candidates"][candidate_id]
        batch_id = uuid.uuid4().hex
        work = self.directory / "work" / batch_id
        work.mkdir(parents=True)
        path = work / "candidate.s"
        path.write_bytes(source.encode("utf-8"))
        batch = {"id": batch_id, "sequence": len(state["batches"]) + 1,
                 "candidate_id": candidate_id, "stage": stage, "status": "running",
                 "attempt_ids": [], "measurement": None}
        batch.update(context or {})
        state["batches"][batch_id] = batch
        self._save(state)
        controller = self

        class RecordingEvaluator:
            def evaluate(self, s_path, with_counters=False):
                controller._check_identity(manifest)
                validator = getattr(evaluator, "validate_contract", None)
                if callable(validator):
                    validator()
                controller._check_deadline(manifest)
                controller._check_eval_budget(manifest, state, 1, stage)
                check_navigation_budget(manifest, state, candidate_id, 1, stage)
                attempt_id = uuid.uuid4().hex
                attempt = {"id": attempt_id, "batch_id": batch_id,
                           "candidate_id": candidate_id, "status": "running",
                           "started_at": time.time(), "result": None,
                           "source_sha256": candidate["artifact"]["sha256"],
                           "guidance": guidance(state, candidate_id)}
                attempt.update(stage=stage, **(context or {}))
                state["attempts"][attempt_id] = attempt
                batch["attempt_ids"].append(attempt_id)
                state["used"]["eval_calls"] += 1
                controller._save(state)  # charge durably BEFORE the external call
                started = time.monotonic()
                try:
                    result = evaluator.evaluate(s_path, with_counters=(stage == "profile"))
                    attempt["result"] = snapshot_result(result)
                    attempt["status"] = "returned"
                except Exception as exc:
                    attempt.update(status="error", error="{}: {}".format(type(exc).__name__, exc))
                    attempt["elapsed_s"] = time.monotonic() - started
                    controller._save(state)
                    raise
                # KeyboardInterrupt/SystemExit/process death intentionally leave
                # a running attempt: recovery must not guess or refund its cost.
                attempt["elapsed_s"] = time.monotonic() - started
                controller._save(state)
                # Preserve the raw return before rejecting a sample collected
                # while the recorded engine/runtime settings were changing.
                controller._check_identity(manifest)
                if callable(validator):
                    validator()
                return result

        result = measure_screen(RecordingEvaluator(), str(path), repeats,
                                expected_sha256=candidate["artifact"]["sha256"])
        batch.update(status=result.status, measurement=result.to_dict())
        self._save(state)
        return copy.deepcopy(batch)

    @staticmethod
    def _comparison_policy(manifest):
        policy = manifest["comparison_policy"]
        if policy is None:
            raise RunError("comparison_not_configured", "freeze a comparison policy when creating a new run")
        return policy

    def _eligible(self, state, candidate_id, reference_id):
        for name in dict.fromkeys(("original", reference_id, candidate_id)):
            self._source(state, name)
            batch = self._latest_batch(state, name)
            if batch is None or batch["status"] != "measured":
                raise RunError("screen_required", name + " must pass its latest screening batch")
        if (state["candidates"][candidate_id]["artifact"]["sha256"] ==
                state["candidates"][reference_id]["artifact"]["sha256"]):
            raise RunError("identical_candidate", "cannot confirm identical candidate and reference bytes")

    def _compare(self, manifest, state, candidate_id, reference_id, evaluator, stage):
        """New samples only; incomplete comparisons cannot promote any version."""
        policy = manifest["comparison_policy"]
        comparison_id = uuid.uuid4().hex
        comparison = {
            "id": comparison_id, "stage": stage, "status": "running",
            "candidate_id": candidate_id, "reference_id": reference_id,
            "candidate_sha256": state["candidates"][candidate_id]["artifact"]["sha256"],
            "reference_sha256": state["candidates"][reference_id]["artifact"]["sha256"],
            "started_at": time.time(), "pairs": [], "analysis": None,
            "verdict": "inconclusive"}
        # Persist the full plan BEFORE any call, so interruption cannot change
        # the reference, pair order, or planned sample size on recovery.
        comparison["planned_pairs"] = planned_pairs(policy, stage)
        for i in range(comparison["planned_pairs"]):
            comparison["pairs"].append({"index": i, "order": list(pair_order(i)),
                                        "batches": {}, "scores": {}})
        state["comparisons"][comparison_id] = comparison
        if stage == "confirm":
            state["confirmation_count"] += 1
        else:
            state["phase"] = "finalizing"
        self._save(state)
        looks = look_sizes(policy, stage)
        for pair in list(comparison["pairs"]):
            for role in pair["order"]:
                name = reference_id if role == "reference" else candidate_id
                batch = self._measure(manifest, state, name, evaluator, 1, stage,
                                      {"comparison_id": comparison_id, "pair_index": pair["index"], "role": role})
                pair["batches"][role] = batch["id"]
                if batch["status"] != "measured":
                    comparison.update(status="measurement_failed", failed_batch_id=batch["id"],
                                      failure_status=batch["status"], finished_at=time.time())
                    return comparison  # caller atomically saves verdict and final/parent state
                pair["scores"][role] = batch["measurement"]["tflops"]
                self._save(state)
            done = pair["index"] + 1
            if policy["method"] == SEQUENTIAL_METHOD and done in looks:
                look = assess_look([p["scores"] for p in comparison["pairs"][:done]],
                                   policy, stage, looks.index(done))
                if look["stop"]:
                    # Later planned pairs were never measured; the analysis
                    # verifies that this is the first stopping look.
                    del comparison["pairs"][done:]
                    break
        comparison["analysis"] = assess_pairs([p["scores"] for p in comparison["pairs"]], policy, stage)
        comparison.update(status="completed", verdict=comparison["analysis"]["verdict"], finished_at=time.time())
        return comparison

    def confirm(self, candidate_id, evaluator, *, evaluation_contract=None):
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            policy = self._comparison_policy(manifest)
            if evaluation_contract is not None and evaluation_contract != manifest["evaluation_contract"]:
                raise RunError("contract_mismatch", "client evaluation contract changed")
            self._source(state, candidate_id)
            candidate_hash = state["candidates"][candidate_id]["artifact"]["sha256"]
            if candidate_hash == manifest["original_sha256"]:
                raise RunError("identical_candidate", "original bytes remain the reference and fallback, not a challenger")
            if candidate_id == state["incumbent_id"]:
                return dict(copy.deepcopy(state["comparisons"][state["incumbent_evidence_id"]]), cached=True)
            reference_id = state["incumbent_id"] or "original"
            reference_hash = state["candidates"][reference_id]["artifact"]["sha256"]
            for previous in state["comparisons"].values():
                if (previous["stage"] == "confirm" and previous["candidate_sha256"] == candidate_hash
                        and previous["reference_sha256"] == reference_hash):
                    return dict(copy.deepcopy(previous), cached=True)
            self._eligible(state, candidate_id, reference_id)
            if state["confirmation_count"] >= policy["max_confirmations"]:
                raise RunError("confirmation_budget_exhausted", "predeclared confirmation attempts exhausted")
            self._check_deadline(manifest)
            self._check_eval_budget(manifest, state, 2 * planned_pairs(policy, "confirm"), "confirm")
            check_comparison_navigation(manifest, state, candidate_id, reference_id,
                                        planned_pairs(policy, "confirm"))
            comparison = self._compare(manifest, state, candidate_id, reference_id, evaluator, "confirm")
            if comparison["verdict"] == "confirmed_gain":
                state["last_gain_sequence"] = len(state["batches"])
                state["incumbent_id"] = candidate_id
                state["incumbent_evidence_id"] = comparison["id"]
                state["exploration_parent_id"] = candidate_id
                state["parent_revision"] += 1
            state["confirmation_status"] = "confirmed_gain" if state["incumbent_id"] else "no_confirmed_gain"
            self._save(state)
            return dict(copy.deepcopy(comparison), cached=False)

    def _finish_final(self, state, comparison=None, reason=None):
        gained = comparison is not None and comparison["verdict"] == "confirmed_gain"
        selected = comparison["candidate_id"] if gained else "original"
        self._source(state, selected)
        artifact = copy.deepcopy(state["candidates"][selected]["artifact"])
        original = self._latest_batch(state, "original")
        state["phase"] = "finished"
        state["final_result"] = {
            "status": "final_recommended" if gained else "original_retained",
            "selected_id": selected, "selected_artifact": artifact,
            "recommendation_id": selected if gained else None,
            "fallback_id": None if gained else "original",
            "comparison_id": comparison["id"] if comparison else None,
            "reason": reason or comparison["verdict"], "finished_at": time.time(),
            "original_screen_status": original["status"] if original else "not_measured",
            "scope": "configured_protocol_on_client_reports; loaded_code_object_and_hardware_environment_unverified"}

    def finalize(self, evaluator, *, evaluation_contract=None):
        """Freeze one choice and finish the run, using only new final samples."""
        with self._locked() as (manifest, state):
            self._check_identity(manifest)
            self._check_pending(state)
            if evaluation_contract is not None and evaluation_contract != manifest["evaluation_contract"]:
                raise RunError("contract_mismatch", "client evaluation contract changed")
            if state["final_result"] is not None:
                self._source(state, state["final_result"]["selected_id"])
                return dict(copy.deepcopy(state["final_result"]), cached=True)
            policy = self._comparison_policy(manifest)
            candidate_id = state["incumbent_id"]
            self._source(state, "original")
            reason = None
            if candidate_id is None:
                reason = "no_confirmed_candidate"
            else:
                try:
                    self._eligible(state, candidate_id, "original")
                    self._check_deadline(manifest)
                    self._check_eval_budget(manifest, state, 2 * planned_pairs(policy, "final"), "final")
                except RunError as exc:
                    if exc.code not in ("screen_required", "wall_time_exhausted", "eval_budget_exhausted"):
                        raise
                    reason = exc.code
            if reason:
                self._finish_final(state, reason=reason)
            else:
                comparison = self._compare(manifest, state, candidate_id, "original", evaluator, "final")
                self._finish_final(state, comparison, reason=comparison.get("failure_status"))
            self._save(state)
            return dict(copy.deepcopy(state["final_result"]), cached=False)

    def select_parent(self, candidate_id):
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            self._source(state, candidate_id)
            batch = self._latest_batch(state, candidate_id)
            if batch is None or batch["status"] != "measured":
                raise RunError("unmeasured_parent", "exploration parent must pass screening in this run")
            state["exploration_parent_id"] = candidate_id
            state["parent_revision"] += 1
            self._save(state)
            return {"exploration_parent_id": candidate_id, "incumbent_id": state["incumbent_id"],
                    "confirmation_status": state["confirmation_status"]}

    def resume(self):
        with self._locked() as (manifest, state):
            self._check_identity(manifest)
            for candidate_id in state["candidates"]:
                self._source(state, candidate_id)
            recovered = []
            for attempt in state["attempts"].values():
                if attempt["status"] == "running":
                    attempt["status"] = "interrupted"
                    recovered.append(attempt["id"])
            for batch in state["batches"].values():
                if batch["status"] == "running":
                    batch["status"] = "interrupted"
            for proposal in state["proposals"]:
                if proposal["status"] == "preparing":
                    proposal["status"] = "interrupted"
                elif proposal["status"] == "import_requested":
                    proposal["status"] = "import_interrupted"
                elif proposal["status"] == "replay_requested":
                    proposal["status"] = "replay_interrupted"
            for operation in state.get("imports", []):
                if operation["status"] == "running":
                    operation["status"] = "interrupted"
            for comparison in state["comparisons"].values():
                if comparison["status"] == "running":
                    comparison.update(status="interrupted", verdict="inconclusive", finished_at=time.time())
                    if comparison["stage"] == "final":
                        self._finish_final(state, comparison, reason="interrupted")
                    elif state["incumbent_id"] is None:
                        state["confirmation_status"] = "no_confirmed_gain"
            self._save(state)
            return {"recovered_attempt_ids": recovered, "used": copy.deepcopy(state["used"]),
                    "exploration_parent_id": state["exploration_parent_id"],
                    "confirmation_status": state["confirmation_status"], "phase": state["phase"],
                    "final_result": copy.deepcopy(state["final_result"])}
