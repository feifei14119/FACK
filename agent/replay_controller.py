"""Persistent, budgeted replay through the controller's normal prepare gate."""
from __future__ import annotations

import copy
import uuid

from agent.history import candidate_chain
from agent.ledger import hypothesis_record
from agent.replay import replay_intent, verify_chain
from agent.search_control import check_reuse_proposal, check_search_open


class ReplayControllerMixin:
    def replay(self, source_candidate_id):
        """Replay a screened candidate's last intent on the current parent.

        Planning reserves one durable CPU proposal. Successful materialization
        goes through `_prepare` and charges its ordinary proposal separately.
        No client call or exploration/incumbent selection occurs here.
        """
        from agent.run import RunError
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            self._check_deadline(manifest)
            check_search_open(manifest, state)
            if state["used"]["proposals"] >= manifest["budget"]["proposal_limit"]:
                raise RunError("proposal_budget_exhausted", "proposal budget exhausted")
            source_candidate = state["candidates"].get(source_candidate_id, {})
            target_id = state["exploration_parent_id"]
            target = state["candidates"][target_id]
            reuse = bool(source_candidate.get("reuse") or target.get("reuse"))
            if reuse:
                check_reuse_proposal(manifest, state)
            provenance = {"mode": "replay", "source_candidate_id": source_candidate_id,
                          "source_candidate_sha256": source_candidate.get("artifact", {}).get("sha256"),
                          "target_parent_id": target_id, "target_parent_sha256": target["artifact"]["sha256"],
                          "original_sha256": manifest["original_sha256"]}
            hypothesis = {"source": "history" if reuse else "replay", "direction": "replay_combination",
                          "hypothesis": "Replay a screened constrained intent on the current exploration parent",
                          "expected_observable": "preserved prior intents and a newly validated client score"}
            request = {"id": uuid.uuid4().hex, "status": "replay_requested", "spec": {"kind": "replay_request"},
                       "parent_id": target_id, "base_sha256": target["artifact"]["sha256"],
                       "reuse": reuse, "reuse_charged": reuse, "provenance": provenance,
                       "hypothesis": hypothesis_record(hypothesis, state)}
            state["used"]["proposals"] += 1
            state["proposals"].append(request)
            self._save(state)
            self._active_replay_request_id = request["id"]
            try:
                self._source(state, source_candidate_id)
                self._source(state, target_id)
                batch = self._latest_batch(state, source_candidate_id)
                if batch is None or batch["status"] != "measured":
                    raise RunError("screen_required", "replay source must pass its latest screening batch")
                source_chain = candidate_chain(state, source_candidate_id, manifest["build_policy"])
                if not source_chain or source_chain[-1]["spec"]["kind"] not in ("layout", "order"):
                    raise RunError("invalid_replay_source", "source must have a successful constrained layout/order proposal")
                target_chain = candidate_chain(state, target_id, manifest["build_policy"])
                original = self._source(state, "original")
                # Authenticate the chosen source artifact, not merely the
                # parent and its declaration of what the last step intended.
                verify_chain(original, source_chain, manifest["build_policy"])
                provenance.update(source_parent_sha256=source_chain[-1]["source_sha256"],
                                  source_chain=copy.deepcopy(source_chain), target_chain=copy.deepcopy(target_chain))
                planned = replay_intent(original, source_chain[:-1], target_chain,
                                        source_chain[-1]["spec"], manifest["build_policy"])
                provenance.update(mapping=planned["mapping"], identity_method=planned["identity_method"],
                                  actual_spec=planned["spec"], expected_candidate_sha256=planned["candidate_sha256"],
                                  replay_diagnostics=planned["diagnostics"])
                request["planning_status"] = "ready"
                self._save(state)
                observation = self._observe(manifest, state, planned["spec"]["region"])
                spec = {key: value for key, value in planned["spec"].items()
                        if key in ("kind", "region", "layout", "order")}
                hypothesis["evidence_refs"] = [{"kind": "candidate", "id": source_candidate_id}]
                prepared = self._prepare(manifest, state, observation["observation_id"],
                                         observation["base_sha256"], spec, hypothesis=hypothesis,
                                         provenance=dict(copy.deepcopy(provenance), request_id=request["id"]))
                proposal = next(p for p in state["proposals"] if p["id"] == prepared["id"])
                proposal["provenance"] = dict(copy.deepcopy(provenance), request_id=request["id"])
                artifact = state["candidates"][prepared["candidate_id"]]["artifact"]
                if artifact["sha256"] != planned["candidate_sha256"]:
                    raise RunError("replay_materialization_mismatch", "normal prepare did not reproduce the planned candidate")
                request.update(status="replay_completed", materialized_proposal_id=prepared["id"],
                               candidate_id=prepared["candidate_id"])
                self._save(state)
                return copy.deepcopy(proposal)
            except BaseException as exc:
                code = getattr(exc, "code", "replay_failed" if isinstance(exc, Exception) else "replay_interrupted")
                request.update(status="replay_rejected" if isinstance(exc, Exception) else "replay_interrupted",
                               error_code=code, error=str(exc))
                if getattr(exc, "diagnostics", None):
                    request["provenance"]["failure_diagnostics"] = copy.deepcopy(exc.diagnostics)
                self._save(state)
                if isinstance(exc, Exception):
                    raise RunError(code, str(exc)) from exc
                raise
            finally:
                del self._active_replay_request_id

    def combine(self, source_candidate_id):
        """Alias for replay; combination uses the same checks and accounting."""
        return self.replay(source_candidate_id)
