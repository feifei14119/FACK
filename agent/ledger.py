"""Bounded experiment explanations; measured evidence remains authoritative."""
from __future__ import annotations

import copy
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def validate_refs(refs, state):
    if not isinstance(refs, list) or len(refs) > 32:
        raise ValueError("evidence_refs must be a list of at most 32 references")
    tables = {key: state[name] for key, name in (
        ("observation", "observations"), ("candidate", "candidates"),
        ("batch", "batches"), ("attempt", "attempts"), ("comparison", "comparisons"))}
    tables["proposal"] = {p["id"]: p for p in state["proposals"]}
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {"kind", "id"} or
                not isinstance(ref["kind"], str) or not isinstance(ref["id"], str) or
                ref["kind"] not in tables or ref["id"] not in tables[ref["kind"]]):
            raise ValueError("evidence reference does not exist in this run")
    return copy.deepcopy(refs)


def hypothesis_record(value, state):
    value = {} if value is None else copy.deepcopy(value)
    allowed = {"hypothesis", "expected_observable", "source", "direction", "evidence_refs"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("unknown hypothesis fields")
    for key in ("hypothesis", "expected_observable"):
        value.setdefault(key, "unspecified")
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 4000:
            raise ValueError(key + " must be a nonempty bounded string")
    value.setdefault("source", "observation")
    if value["source"] not in ("observation", "profile", "knowledge", "history", "replay"):
        raise ValueError("unknown hypothesis source")
    value.setdefault("direction", "manual")
    if not isinstance(value["direction"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value["direction"]):
        raise ValueError("direction must be a stable lowercase identifier")
    value["evidence_refs"] = validate_refs(value.get("evidence_refs", []), state)
    return value


def ledger_snapshot(manifest, state):
    rows = []
    for proposal in state["proposals"]:
        row = copy.deepcopy(proposal)
        candidate = proposal.get("candidate_id")
        row["batches"] = [copy.deepcopy(b) for b in state["batches"].values()
                          if candidate is not None and b["candidate_id"] == candidate]
        row["comparisons"] = [copy.deepcopy(c) for c in state.get("comparisons", {}).values()
                               if candidate is not None and candidate in (c["candidate_id"], c["reference_id"])]
        row["evidence_scope"] = "this_intent_parent_contract_only; no_global_direction_verdict"
        rows.append(row)
    return {"schema_version": 1, "run_id": manifest["run_id"], "revision": state["revision"],
            "rows": rows, "annotations": copy.deepcopy(state.get("annotations", [])),
            "imports": copy.deepcopy(state.get("imports", [])),
            "final_result": copy.deepcopy(state.get("final_result"))}
