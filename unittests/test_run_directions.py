"""CPU search navigation: policy gates and engine-checked small proposals."""
import copy
import hashlib
import json
from unittest import mock

import pytest

from agent.directions import MAX_POLICY_INTEGER, suggestions, validate_search_policy
from agent.session import AgentSession, ProposeOutcome
from reorder.model import Kind
from search import driver
from unittests.test_session import MFMA, _BIGDAG_KERNEL, _SYNTH


BUILD_POLICY = {"opt_level": 1, "protect_prefetch": False, "strict_verify": False}
MIXED = """.text
k:
  {m} v[36:39], a[0:1], a[2:3], v[36:39]
  {m} v[40:43], a[4:5], a[6:7], v[40:43]
  buffer_load_dwordx4 v[4:7], v64, s[0:3], 0 offen
  v_add_u32 v100, v101, v102
  {m} v[44:47], a[8:9], a[10:11], v[44:47]
  {m} v[48:51], a[12:13], a[14:15], v[48:51]
  {m} v[52:55], a[16:17], a[18:19], v[52:55]
  s_endpgm
""".format(m=MFMA)


def test_policy_defaults_are_complete_independent_and_profile_opt_in():
    policy = validate_search_policy()
    assert policy == {"direction_eval_call_limit": None, "profile_call_limit": 0,
                      "stagnation_limit": None, "reuse_proposal_limit": None,
                      "reuse_eval_call_limit": None, "independent_eval_reserve": 0,
                      "candidate_providers": None, "candidate_attempt_limit": 96}
    policy["profile_call_limit"] = 7
    assert validate_search_policy()["profile_call_limit"] == 0
    original = {"profile_call_limit": 2, "reuse_proposal_limit": 0, "stagnation_limit": 1}
    frozen = validate_search_policy(original)
    original["profile_call_limit"] = 100
    assert frozen["profile_call_limit"] == 2
    assert json.loads(json.dumps(frozen)) == frozen


@pytest.mark.parametrize("value", [[], True, "policy", {"unknown": 1},
    {"profile_call_limit": True}, {"profile_call_limit": -1}, {"profile_call_limit": 1.0},
    {"direction_eval_call_limit": "5"}, {"direction_eval_call_limit": -1},
    {"stagnation_limit": 0}, {"stagnation_limit": False},
    {"reuse_proposal_limit": -1}, {"reuse_eval_call_limit": float("inf")},
    {"independent_eval_reserve": None}, {"independent_eval_reserve": False},
    {"independent_eval_reserve": MAX_POLICY_INTEGER + 1}])
def test_policy_rejects_ambiguous_and_out_of_range_limits(value):
    with pytest.raises(ValueError):
        validate_search_policy(value)


def test_explicit_unlimited_and_zero_policy_values():
    assert validate_search_policy({"profile_call_limit": None})["profile_call_limit"] is None
    for name in ("profile_call_limit", "direction_eval_call_limit", "reuse_proposal_limit",
                 "reuse_eval_call_limit", "independent_eval_reserve"):
        assert validate_search_policy({name: 0})[name] == 0
        assert validate_search_policy({name: MAX_POLICY_INTEGER})[name] == MAX_POLICY_INTEGER


def assert_proposals(source, rows, region="loop"):
    session = AgentSession(source, None, region=region, protect_prefetch=False)
    normalized, _ = driver.build_candidate(source, dict(BUILD_POLICY, kind="ladder", level=1, region=region))
    seen = {source, normalized}
    for row in rows:
        assert {"direction", "spec", "hypothesis", "provider", "candidate_sha256"} <= set(row)
        spec = row["spec"]
        assert spec["region"] == region
        assert not (set(spec) & set(BUILD_POLICY))
        if spec["kind"] == "layout":
            assert sum(len(v) for v in spec["layout"].values()) == 1
            report = session.propose([{int(k): v for k, v in spec["layout"].items()}])[0]
            assert report.legal and not report.skipped
        else:
            assert len(spec["order"]) == 2
            report = session.propose_orders([spec["order"]])[0]
            assert report["legal"] and not report["skipped"]
        candidate, ok = driver.build_candidate(source, dict(spec, **BUILD_POLICY))
        assert ok and candidate not in seen
        assert row["candidate_sha256"] == hashlib.sha256(candidate.encode()).hexdigest()
        seen.add(candidate)
        assert "test" in row["hypothesis"]


def test_anchored_suggestions_are_bounded_deterministic_and_unique():
    rows = suggestions(_SYNTH, "loop", BUILD_POLICY, n=6)
    assert len(rows) == 6
    assert rows == suggestions(_SYNTH, "loop", BUILD_POLICY, n=6)
    assert_proposals(_SYNTH, rows)
    assert json.loads(json.dumps(rows)) == rows


def test_available_directions_get_turns_before_local_refinement():
    rows = suggestions(MIXED, "loop", BUILD_POLICY, n=4)
    assert {row["direction"] for row in rows} == {
        "memory_early", "memory_late", "alu_early", "alu_late"}
    assert_proposals(MIXED, rows)


def test_dependency_gate_rejects_gap_before_address_producer():
    source = _SYNTH.replace(
        "  {} v[44:47]".format(MFMA), "  v_mov_b32 v64, 0\n  {} v[44:47]".format(MFMA))
    rows = suggestions(source, "loop", BUILD_POLICY, n=16)
    assert rows
    editor = AgentSession(source, None, protect_prefetch=False)._editor()
    first_load = next(i for i in editor.order if editor.kind_of(i) is Kind.VMEM_LOAD)
    requests = [(int(slot), ids) for row in rows for slot, ids in row["spec"]["layout"].items()
                if first_load in ids]
    assert requests and all(slot >= 2 for slot, _ in requests)
    assert_proposals(source, rows)


def test_anchorless_uses_existing_scheduler_and_small_order_intents(monkeypatch):
    # More than the existing 64-IID propose limit: submitting a full scheduler
    # permutation would fail, while local adjacency trials remain usable.
    extra = "\n".join("  v_mov_b32 v{}, 0".format(i) for i in range(32, 112))
    source = _BIGDAG_KERNEL.replace("  s_endpgm", extra + "\n  s_endpgm")
    original = AgentSession.suggest_orders
    calls = []

    def tracked(session, *args, **kwargs):
        calls.append(kwargs)
        return original(session, *args, **kwargs)

    monkeypatch.setattr(AgentSession, "suggest_orders", tracked)
    rows = suggestions(source, "loop", BUILD_POLICY)
    assert calls == [{"n": 3}]
    assert rows and all(row["spec"]["kind"] == "order" for row in rows)
    assert_proposals(source, rows)


def test_suggestions_do_not_observe_profile_read_priors_or_write_knowledge(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("CPU suggestions must not read priors, evaluate, profile or write")

    monkeypatch.setattr(AgentSession, "observe", forbidden)
    monkeypatch.setattr(AgentSession, "commit_and_eval", forbidden)
    monkeypatch.setattr("agent.knowledge.seed_search_plan", forbidden)
    monkeypatch.setattr("agent.knowledge.log_experiment", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    policy = copy.deepcopy(BUILD_POLICY)
    assert suggestions(_SYNTH, "loop", policy)
    assert suggestions(_BIGDAG_KERNEL, "loop", policy)
    assert policy == BUILD_POLICY


@pytest.mark.parametrize("kind", ["layout", "order"])
def test_skipped_proposals_never_escape_as_suggestions(monkeypatch, kind):
    if kind == "layout":
        source = _SYNTH
        monkeypatch.setattr(AgentSession, "propose", lambda *args: [
            ProposeOutcome(layout={}, legal=True, skipped=[{"reason": "fake blocked"}])])
    else:
        source = _BIGDAG_KERNEL
        monkeypatch.setattr(AgentSession, "propose_orders", lambda *args: [
            {"legal": True, "skipped": [{"reason": "fake blocked"}]}])
    assert suggestions(source, "loop", BUILD_POLICY) == []


def test_materialized_rejection_and_normalization_only_are_filtered(monkeypatch):
    for text, ok in (("", False), (_SYNTH, True), ("normalized", True)):
        with mock.patch.object(driver, "build_candidate", return_value=(text, ok)):
            assert suggestions(_SYNTH, "loop", BUILD_POLICY) == []


def test_empty_budget_and_single_anchor_do_not_invent_moves(monkeypatch):
    assert suggestions(_SYNTH, "loop", BUILD_POLICY, n=0) == []
    source = ".text\nk:\n  {} v[36:39], a[0:1], a[2:3], v[36:39]\n  s_endpgm\n".format(MFMA)
    assert suggestions(source, "loop", BUILD_POLICY) == []


@pytest.mark.parametrize("n", [True, -1, 1.0, 33, None])
def test_invalid_suggestion_count_is_rejected(n):
    with pytest.raises(ValueError):
        suggestions(_SYNTH, "loop", BUILD_POLICY, n=n)


@pytest.mark.parametrize("policy", [None, {}, dict(BUILD_POLICY, opt_level=True),
    dict(BUILD_POLICY, opt_level=2), dict(BUILD_POLICY, protect_prefetch=1),
    dict(BUILD_POLICY, extra=0)])
def test_suggestions_cannot_change_or_guess_build_policy(policy):
    with pytest.raises(ValueError):
        suggestions(_SYNTH, "loop", policy)
