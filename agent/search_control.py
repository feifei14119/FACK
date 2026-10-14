"""Search navigation limits and optional profiling on the persistent run."""
from __future__ import annotations

import copy


def guidance(state, candidate_id):
    candidate = state["candidates"][candidate_id]
    return {"direction": candidate.get("direction", "baseline" if candidate_id in ("original", "normalized") else "manual"),
            "reuse": bool(candidate.get("reuse", False))}


def search_status(manifest, state):
    attempts = list(state["attempts"].values())
    directions, reuse_calls, independent = {}, 0, 0
    for attempt in attempts:
        meta = attempt.get("guidance", {})
        if meta.get("reuse"):
            reuse_calls += 1
        if attempt.get("stage", "screen") == "screen":
            direction = meta.get("direction", "baseline")
            directions[direction] = directions.get(direction, 0) + 1
            if not meta.get("reuse") and attempt["candidate_id"] not in ("original", "normalized"):
                independent += 1
    last_gain = state.get("last_gain_sequence", 0)
    first_valid = {}
    for batch in sorted(state["batches"].values(), key=lambda b: b["sequence"]):
        if batch.get("stage", "screen") == "screen" and batch["status"] == "measured" and batch["candidate_id"] != "original":
            identity = state["candidates"][batch["candidate_id"]]["artifact"]["sha256"]
            if identity != manifest["original_sha256"]:
                first_valid.setdefault(identity, batch["sequence"])
    stagnant = sum(sequence > last_gain for sequence in first_valid.values())
    policy = manifest.get("search_policy", {})
    limit = policy.get("stagnation_limit")
    profiles = [b for b in state["batches"].values() if b.get("stage", "screen") == "profile"]
    current = [b for b in profiles if b["candidate_id"] == state["exploration_parent_id"] and
               b.get("parent_revision") == state["parent_revision"] and b.get("profile_status") == "available"]
    return {"direction_eval_calls": directions, "reuse_eval_calls": reuse_calls,
            "reuse_proposals": sum(bool(p.get("reuse_charged", p.get("reuse"))) for p in state["proposals"]),
            "independent_eval_calls": independent,
            "profile_calls": sum(a.get("stage", "screen") == "profile" for a in attempts),
            "stagnation_count": stagnant, "search_stopped": limit is not None and stagnant >= limit,
            "current_profile_id": max(current, key=lambda b: b["sequence"])["id"] if current else None,
            "profile_needs_refresh": not bool(current)}


def check_search_open(manifest, state):
    from agent.run import RunError
    if search_status(manifest, state)["search_stopped"]:
        raise RunError("search_stagnated", "unique valid screens reached the frozen stagnation limit; confirm or final may still run")


def check_navigation_budget(manifest, state, candidate_id, count, stage):
    from agent.run import RunError
    policy = manifest.get("search_policy", {})
    usage = search_status(manifest, state)
    meta = guidance(state, candidate_id)
    if stage == "screen" and candidate_id not in ("original", "normalized"):
        limit = policy.get("direction_eval_call_limit")
        if limit is not None and usage["direction_eval_calls"].get(meta["direction"], 0) + count > limit:
            raise RunError("direction_budget_exhausted", "direction screen-call budget exhausted")
    profile_limit = policy.get("profile_call_limit", 0)
    if stage == "profile" and profile_limit is not None and usage["profile_calls"] + count > profile_limit:
        raise RunError("profile_budget_exhausted", "profiling is disabled or its frozen call limit is exhausted")
    # Final is protected separately and must not be blocked by navigation caps.
    if meta["reuse"] and stage != "final":
        limit = policy.get("reuse_eval_call_limit")
        if limit is not None and usage["reuse_eval_calls"] + count > limit:
            raise RunError("reuse_budget_exhausted", "knowledge/history evaluation allowance exhausted")
    if stage != "final" and (meta["reuse"] or stage == "profile"):
        reserved = max(0, policy.get("independent_eval_reserve", 0) - usage["independent_eval_calls"])
        budget = manifest["budget"]
        available = budget["eval_call_limit"] - budget["final_eval_reserve"] - state["used"]["eval_calls"]
        if count + reserved > available:
            raise RunError("independent_reserve", "independent current-observation search calls are reserved")


def check_reuse_proposal(manifest, state):
    from agent.run import RunError
    limit = manifest.get("search_policy", {}).get("reuse_proposal_limit")
    if limit is not None and search_status(manifest, state)["reuse_proposals"] >= limit:
        raise RunError("reuse_proposal_budget_exhausted", "knowledge/history proposal allowance exhausted")


def charge_reuse_proposal(manifest, state, proposal):
    # A duplicate of a historical artifact cannot be relabelled independent.
    proposal["reuse"] = True
    check_reuse_proposal(manifest, state)
    proposal["reuse_charged"] = True


def check_comparison_navigation(manifest, state, candidate_id, reference_id, pairs):
    from agent.run import RunError
    usage = search_status(manifest, state)
    policy = manifest.get("search_policy", {})
    reused_sides = sum(guidance(state, cid)["reuse"] for cid in (candidate_id, reference_id))
    limit = policy.get("reuse_eval_call_limit")
    if limit is not None and usage["reuse_eval_calls"] + reused_sides * pairs > limit:
        raise RunError("reuse_budget_exhausted", "insufficient reuse allowance for complete confirmation")
    if reused_sides:
        reserved = max(0, policy.get("independent_eval_reserve", 0) - usage["independent_eval_calls"])
        budget = manifest["budget"]
        available = budget["eval_call_limit"] - budget["final_eval_reserve"] - state["used"]["eval_calls"]
        if 2 * pairs + reserved > available:
            raise RunError("independent_reserve", "complete confirmation would consume independent search reserve")


class SearchControllerMixin:
    def suggest(self, region=None, n=6):
        from agent.directions import suggestions, MAX_SUGGESTIONS
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            self._check_deadline(manifest)
            check_search_open(manifest, state)
            if type(n) is not int or not 0 <= n <= MAX_SUGGESTIONS:
                raise ValueError("suggestion count must be between 0 and 32")
            obs = self._observe(manifest, state, region)
            choices = suggestions(self._source(state, obs["parent_id"]), obs["region"], manifest["build_policy"],
                                  n=MAX_SUGGESTIONS if n else 0)
            usage = search_status(manifest, state)
            limit = manifest["search_policy"]["direction_eval_call_limit"]
            if limit is not None:
                choices = [c for c in choices if usage["direction_eval_calls"].get(c["direction"], 0)
                           + manifest["perf_repeats"] <= limit]
            # Untried directions first; never infer a direction-wide regression
            # from a failed candidate or a noisy score.
            choices.sort(key=lambda c: usage["direction_eval_calls"].get(c["direction"], 0))
            choices = choices[:n]
            for item in choices:
                item["hypothesis"] = {"hypothesis": item["hypothesis"],
                                      "expected_observable": "improved client score; profile can separately test stall explanation",
                                      "direction": item["direction"], "source": "observation",
                                      "evidence_refs": [{"kind": "observation", "id": obs["observation_id"]}]}
            return {"observation": obs, "suggestions": choices, "search": usage,
                    "scope": "CPU intent suggestions; require prepare, screen and independent confirmation"}

    def profile(self, candidate_id, evaluator, *, evaluation_contract=None):
        from agent.run import RunError
        with self._locked() as (manifest, state):
            self._ready(manifest, state)
            check_search_open(manifest, state)
            if evaluation_contract is not None and evaluation_contract != manifest["evaluation_contract"]:
                raise RunError("contract_mismatch", "client evaluation contract changed")
            self._source(state, candidate_id)
            if state["candidates"][candidate_id]["static_ok"] is False:
                raise RunError("verify_failed", "candidate failed static verification")
            for name in dict.fromkeys(("original", candidate_id)):
                baseline = self._latest_batch(state, name)
                if baseline is None or baseline["status"] != "measured":
                    raise RunError("screen_required", name + " must pass screening before optional profiling")
            self._check_deadline(manifest)
            self._check_eval_budget(manifest, state, 1, "profile")
            check_navigation_budget(manifest, state, candidate_id, 1, "profile")
            batch = self._measure(manifest, state, candidate_id, evaluator, 1, "profile",
                                  {"parent_revision": state["parent_revision"]})
            raw = [state["attempts"][key].get("result") or {} for key in batch["attempt_ids"]]
            available = batch["status"] == "measured" and any(r.get("counters") for r in raw)
            stored = state["batches"][batch["id"]]
            stored["profile_status"] = "available" if available else "unavailable"
            stored["scope"] = "navigation_only; profile timings are excluded from screen/confirm/final"
            self._save(state)
            return copy.deepcopy(stored)
