"""Register compatible historical recipes through the current run's CPU gates.

Detached observations bind each step without changing exploration_parent_id or
incumbent. No evaluator, sample transfer, parent selection or promotion occurs.
"""
from __future__ import annotations

import copy
from pathlib import Path
import time
import uuid

from agent.history import HistoryError, load_history
from agent.replay import ReplayError, source_sha256, verify_chain
from agent.search_control import check_search_open


def _evidence_ref(recipe):
    return {"history_run_dir": recipe["history_run_dir"],
            "history_run_id": recipe["history_run_id"],
            "manifest_sha256": recipe["manifest_sha256"],
            "state_sha256": recipe["state_sha256"],
            "candidate_id": recipe["candidate_id"],
            "candidate_sha256": recipe["candidate_sha256"],
            "comparison_id": recipe["evidence_ref"]["comparison_id"],
            "stage": recipe["evidence_ref"]["stage"]}


class HistoryControllerMixin:
    def history(self, directory, candidate_id=None):
        """Read a verified recipe only after checking this live run's identity."""
        from agent.run import RunError
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            self._check_deadline(manifest)
            self._source(state, "original")
            try:
                return load_history(directory, manifest, candidate_id)
            except (HistoryError, ReplayError) as exc:
                raise RunError(exc.code, str(exc)) from exc

    def warm_start(self, directory, candidate_id=None):
        """Rebuild and register each history step, leaving current selection intact.

        _prepare(detached=True) must still charge proposal/reuse budgets and
        check observation revision, source digest, policy and original findings.
        _charge_history_request charges one request even if verification fails.
        _charge_import_normalized handles the already-created normalization as
        a charged proposal and returns the usual proposal record.
        """
        from agent.run import RunError
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            self._check_deadline(manifest)
            check_search_open(manifest, state)
            action = {"id": uuid.uuid4().hex, "kind": "history_warm_start", "status": "running",
                      "started_at": time.time(), "history_run_dir": str(Path(directory).resolve()),
                      "requested_candidate_id": candidate_id, "registered": [],
                      "source_evidence_ref": None, "measurements_imported": False,
                      "requires_evaluation": True}
            request = self._charge_history_request(manifest, state, action)
            action["request_proposal_id"] = request["id"]
            state.setdefault("imports", []).append(action)
            self._save(state)
            self._active_history_import_id = action["id"]
            try:
                recipe = load_history(directory, manifest, candidate_id)
                original = self._source(state, "original")
                rebuilt = verify_chain(original, recipe["chain"], manifest["build_policy"])
                if (not recipe["chain"] or rebuilt["original_sha256"] != manifest["original_sha256"] or
                        rebuilt["sha256"] != recipe["candidate_sha256"]):
                    raise RunError("history_mismatch", "history does not rebuild from this run's original")
                action["source_evidence_ref"] = _evidence_ref(recipe)
                request["provenance"]["source_evidence_ref"] = copy.deepcopy(action["source_evidence_ref"])
                action["recipe"] = copy.deepcopy(recipe["chain"])
                self._save(state)
                parent = "original"
                for index, step in enumerate(recipe["chain"]):
                    self._check_identity(manifest)
                    self._check_deadline(manifest)
                    action["active_step_index"] = index
                    if source_sha256(self._source(state, parent)) != step["source_sha256"]:
                        raise RunError("history_mismatch", "current import parent differs from verified recipe")
                    spec = step["spec"]
                    provenance = {"import_id": action["id"], "step_index": index,
                                  "source_evidence_ref": copy.deepcopy(action["source_evidence_ref"])}
                    if spec["kind"] == "ladder":
                        normalized = state["candidates"]["normalized"]
                        if (index != 0 or normalized.get("static_ok") is not True or
                                source_sha256(self._source(state, "normalized")) != step["candidate_sha256"]):
                            raise RunError("history_mismatch", "current normalization differs from verified history")
                        proposal = self._charge_import_normalized(manifest, state, provenance)
                    else:
                        obs = self._observe(manifest, state, spec["region"], parent_id=parent)
                        intent = {"kind": spec["kind"], "region": spec["region"],
                                  spec["kind"]: copy.deepcopy(spec[spec["kind"]])}
                        hypothesis = {"source": "history", "direction": "history_warm_start",
                                      "hypothesis": "Rebuild verified historical intent; import {} step {}".format(action["id"], index),
                                      "expected_observable": "current-run screening and confirmation must establish any gain",
                                      "evidence_refs": [{"kind": "observation", "id": obs["observation_id"]}]}
                        proposal = self._prepare(manifest, state, obs["observation_id"], obs["base_sha256"],
                                                 intent, hypothesis=hypothesis, detached=True,
                                                 provenance=provenance)
                    actual_id = proposal["candidate_id"]
                    actual_hash = source_sha256(self._source(state, actual_id))
                    action["registered"].append({"step_index": index, "proposal_id": proposal["id"],
                                                 "candidate_id": actual_id, "parent_id": parent,
                                                 "status": proposal["status"], "sha256": actual_hash,
                                                 "expected_sha256": step["candidate_sha256"]})
                    self._save(state)
                    if actual_hash != step["candidate_sha256"]:
                        raise RunError("history_mismatch", "registered candidate differs from verified history")
                    parent = actual_id
                action.update(status="prepared", candidate_id=parent, finished_at=time.time())
                request.update(status="import_prepared", candidate_id=parent, finished_at=action["finished_at"])
                action.pop("active_step_index", None)
                self._save(state)
                return copy.deepcopy(action)
            except BaseException as exc:
                action.update(status="interrupted" if not isinstance(exc, Exception) else "rejected",
                              error_code=getattr(exc, "code", "history_import_failed"),
                              error=str(exc), finished_at=time.time())
                request.update(status="import_" + action["status"], error_code=action["error_code"],
                               error=action["error"], finished_at=action["finished_at"])
                self._save(state)
                if isinstance(exc, (HistoryError, ReplayError)):
                    raise RunError(exc.code, str(exc)) from exc
                raise
            finally:
                del self._active_history_import_id
