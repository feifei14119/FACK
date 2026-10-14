"""Constrained replay and combination using CPU-only real reorder fixtures."""
import copy

import pytest

from agent import replay
from agent.replay import ReplayError, remap_spec, replay_intent, source_sha256, verify_chain
from unittests.test_session import _SYNTH, _loads


POLICY = {"opt_level": 1, "protect_prefetch": False, "strict_verify": False}


def layout(slot=0, load=0):
    return {"kind": "layout", "region": "loop", "layout": {str(slot): [_loads(_SYNTH)[1][load]]}}


def step(result):
    return {key: copy.deepcopy(result[key]) for key in ("spec", "source_sha256", "candidate_sha256")}


def test_sibling_combination_rebuilds_both_parents_and_preserves_intents():
    first = replay_intent(_SYNTH, [], [], layout(), POLICY)
    combined = replay_intent(_SYNTH, [], [step(first)], layout(1, 1), POLICY)
    assert combined["source_sha256"] == first["candidate_sha256"]
    assert combined["candidate_sha256"] != first["candidate_sha256"]
    assert combined["mapping"]["3"] == 4  # an anchor acquired a new IID
    assert combined["identity_method"] == "unique_label_and_raw_instruction"
    assert combined["diagnostics"]["new_findings"] == []
    assert combined["requires_evaluation"] is True
    rebuilt = verify_chain(_SYNTH, [step(first), step(combined)], POLICY)
    assert rebuilt["source"] == combined["source"]
    assert rebuilt["original_sha256"] == source_sha256(_SYNTH)


def test_conflicting_sibling_intent_cannot_undo_target_chain():
    first = replay_intent(_SYNTH, [], [], layout(), POLICY)
    with pytest.raises(ReplayError) as exc:
        replay_intent(_SYNTH, [], [step(first)], layout(1, 0), POLICY)
    assert exc.value.code == "intent_conflict"
    assert verify_chain(_SYNTH, [step(first)], POLICY)["source"] == first["source"]


@pytest.mark.parametrize("field,code", [("source_sha256", "ancestry_mismatch"),
                                       ("candidate_sha256", "artifact_mismatch")])
def test_chain_does_not_import_text_or_trust_claimed_sha(field, code):
    first = replay_intent(_SYNTH, [], [], layout(), POLICY)
    forged = step(first)
    forged[field] = "0" * 64
    with pytest.raises(ReplayError) as exc:
        verify_chain(_SYNTH, [forged], POLICY)
    assert exc.value.code == code
    forged = dict(step(first), source=first["source"])
    with pytest.raises(ReplayError, match="steps require"):
        verify_chain(_SYNTH, [forged], POLICY)


def test_policy_changes_and_arbitrary_transform_kinds_are_rejected():
    for spec, code in ((dict(layout(), opt_level=0), "policy_mismatch"),
                       ({"kind": "compact", "region": "loop"}, "invalid_spec"),
                       (dict(layout(), strict_verify=0), "policy_mismatch"),
                       ({"kind": "order", "region": "loop", "order": [3, 3]}, "invalid_spec")):
        with pytest.raises(ReplayError) as exc:
            replay_intent(_SYNTH, [], [], spec, POLICY)
        assert exc.value.code == code


def test_region_membership_and_exact_operands_must_match():
    changed = _SYNTH.replace("v64,", "v68,")
    with pytest.raises(ReplayError) as exc:
        remap_spec(_SYNTH, changed, layout(), POLICY)
    assert exc.value.code == "region_mismatch"


@pytest.mark.parametrize("target", ["gfx900", "gfx942:xnack+"])
def test_independent_mapping_rejects_architecture_or_target_feature_changes(target):
    original = '.amdgcn_target "amdgcn-amd-amdhsa--gfx942:xnack-"\n' + _SYNTH
    changed = original.replace("gfx942:xnack-", target)
    # Reject the target contract before region IDs or classifier behavior can
    # accidentally make otherwise identical instruction text look compatible.
    with pytest.raises(ReplayError) as exc:
        remap_spec(original, changed, layout(), POLICY)
    assert exc.value.code == "target_mismatch"


def test_anchorless_order_replays_through_the_existing_engine():
    source = ".text\nk:\n  s_mov_b32 s0, 1\n  s_mov_b32 s1, 2\n  s_mov_b32 s2, 3\n  s_endpgm\n"
    result = replay_intent(source, [], [], {"kind": "order", "region": "body", "order": [4, 2]}, POLICY)
    assert result["source"].index("s2, 3") < result["source"].index("s0, 1")
    assert verify_chain(source, [step(result)], POLICY)["source"] == result["source"]


def test_engine_owned_wait_rebuild_does_not_break_payload_mapping():
    source = _SYNTH.replace("  s_endpgm", "  s_waitcnt vmcnt(0)\n  s_endpgm")
    result = replay_intent(source, [], [], layout(), POLICY)
    assert "s_waitcnt" not in result["source"]
    assert verify_chain(source, [step(result)], POLICY)["source"] == result["source"]


def test_unknown_iids_fail_before_materialization():
    with pytest.raises(ReplayError) as exc:
        replay_intent(_SYNTH, [], [], {"kind": "order", "region": "loop", "order": [99999]}, POLICY)
    assert exc.value.code == "invalid_spec"


def test_repeated_raw_instruction_without_unique_context_is_not_guessed():
    source = ".text\nk:\n  v_mov_b32 v0, 0\n  v_mov_b32 v0, 0\n  s_endpgm\n"
    spec = {"kind": "order", "region": "body", "order": [2]}
    assert remap_spec(source, source, spec, POLICY)["mapping"] == {"2": 2}
    with pytest.raises(ReplayError) as exc:
        remap_spec(source, "\n" + source, spec, POLICY)
    assert exc.value.code == "ambiguous_identity"


def test_distinct_label_context_disambiguates_exact_repeated_instruction():
    source = ".text\nk:\n  v_mov_b32 v0, 0\n.Lother:\n  v_mov_b32 v0, 0\n  s_endpgm\n"
    mapped = remap_spec(source, "\n" + source,
                        {"kind": "order", "region": "body", "order": [2]}, POLICY)
    assert mapped["mapping"] == {"2": 3}


def test_invalid_or_skipped_placements_are_not_silently_materialized():
    with pytest.raises(ReplayError) as exc:
        replay_intent(_SYNTH, [], [], layout(999), POLICY)
    assert exc.value.code == "proposal_rejected"
    assert exc.value.diagnostics["skipped"]


def test_chain_cannot_expand_original_static_warning_allowance(monkeypatch):
    values = iter([("middle", True), ("last", True)])
    monkeypatch.setattr(replay.driver, "build_candidate", lambda *args: next(values))
    monkeypatch.setattr(replay, "_propose", lambda *args: {"legal": True, "skipped": []})
    monkeypatch.setattr(replay, "_findings", lambda source, original:
                        ["original gap"] + (["new gap"] if source == "last" else []))
    chain = [{"spec": layout(), "source_sha256": source_sha256(a), "candidate_sha256": source_sha256(b)}
             for a, b in (("original", "middle"), ("middle", "last"))]
    with pytest.raises(ReplayError) as exc:
        verify_chain("original", chain, POLICY)
    assert exc.value.code == "new_static_findings"
    assert exc.value.diagnostics["original_findings"] == ["original gap"]
    assert exc.value.diagnostics["new_findings"] == ["new gap"]


def test_normalization_is_only_allowed_at_chain_root():
    spec = dict(POLICY, kind="ladder", level=1, region="loop")
    text, ok = replay.driver.build_candidate(_SYNTH, spec)
    assert ok
    normalized = {"spec": spec, "source_sha256": source_sha256(_SYNTH),
                  "candidate_sha256": source_sha256(text)}
    assert verify_chain(_SYNTH, [normalized], POLICY)["source"] == text
    with pytest.raises(ReplayError) as exc:
        verify_chain(_SYNTH, [normalized, dict(normalized, source_sha256=source_sha256(text))], POLICY)
    assert exc.value.code == "invalid_spec"
