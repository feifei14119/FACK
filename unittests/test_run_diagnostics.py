"""Stable static evidence and observed byte changes, entirely on CPU."""
import json

import pytest

from agent import diagnostics
from agent.diagnostics import actual_changes, diagnose_candidate, raw_findings
from reorder import parser, regions
from reorder.verifier import Verifier
from search import driver
from unittests.test_session import _SYNTH, _loads


UNSYNCED = """.text
k:
  buffer_load_dword v0, v1, s[0:3], 0 offen
  v_add_u32 v2, v0, 1
  s_endpgm
"""


def test_uses_complete_existing_verifier_and_keeps_raw_findings():
    program = parser.parse(UNSYNCED)
    target = driver._default_target(program)
    expected = Verifier(target, reference=parser.parse(UNSYNCED),
                        analysis=regions.analyze(program, target)).verify(program)
    assert raw_findings(UNSYNCED, UNSYNCED) == sorted(expected.violations)
    assert expected.violations


def test_original_issue_survives_line_shift_with_stable_operand_bound_identity():
    candidate = "\n// source line shift\n" + UNSYNCED
    result = diagnose_candidate(UNSYNCED, UNSYNCED, candidate)
    assert result["ok_vs_original"] is True
    assert not result["new_findings"]
    original = result["original"]["findings"][0]
    inherited = result["inherited_findings"][0]
    assert inherited["id"] == original["id"]
    assert inherited["line_indices"] != original["line_indices"]
    assert inherited["instructions"][0] == {
        "label": "k", "opcode": "v_add_u32", "operands": ["v2", "v0", "1"]}
    assert "line <instruction>" in inherited["identity"]["message"]
    assert json.loads(json.dumps(result)) == result


def test_changed_operand_is_a_new_finding_not_a_reused_warning_allowance():
    candidate = UNSYNCED.replace("v2, v0, 1", "v3, v0, 1")
    result = diagnose_candidate(UNSYNCED, UNSYNCED, candidate)
    assert result["ok_vs_original"] is False
    assert len(result["new_findings"]) == 1
    assert len(result["resolved_findings"]) == 1
    assert result["new_findings"][0]["id"] != result["original"]["findings"][0]["id"]


def test_parent_issue_never_expands_fixed_original_warning_allowance():
    parent = UNSYNCED.replace("  s_endpgm", "  v_add_u32 v3, v0, 2\n  s_endpgm")
    candidate = "// next round\n" + parent
    first = diagnose_candidate(UNSYNCED, UNSYNCED, parent)
    second = diagnose_candidate(UNSYNCED, parent, candidate)
    assert len(first["new_findings"]) == len(second["new_findings"]) == 1
    assert first["new_findings"][0]["id"] == second["new_findings"][0]["id"]
    assert len(second["parent_new_findings"]) == 1
    assert second["allowance_source_sha256"] == first["original"]["sha256"]
    assert second["ok_vs_original"] is False


def test_repaired_original_finding_and_strict_mode_are_distinguished():
    candidate = UNSYNCED.replace("  v_add", "  s_waitcnt vmcnt(0)\n  v_add")
    repaired = diagnose_candidate(UNSYNCED, UNSYNCED, candidate)
    assert repaired["ok_vs_original"] is True
    assert len(repaired["resolved_findings"]) == 1
    assert repaired["candidate"]["verifier_ok"] is True
    strict = diagnose_candidate(UNSYNCED, UNSYNCED, UNSYNCED, strict_verify=True)
    assert strict["inherited_findings"] and not strict["ok_vs_original"]


def test_duplicate_warning_occurrences_cannot_hide_behind_one_original_id():
    candidate = UNSYNCED.replace("  s_endpgm", "  v_add_u32 v2, v0, 1\n  s_endpgm")
    result = diagnose_candidate(UNSYNCED, UNSYNCED, candidate)
    assert result["ok_vs_original"] is False
    assert len(result["new_findings"]) == 2
    assert all(finding["identity_ambiguous"] for finding in result["new_findings"])
    assert result["unmatched_original_findings"]
    assert not result["resolved_findings"]


def test_global_reference_sensitive_invariant_remains_fixed_to_original():
    original = ".text\nk:\n  s_barrier\n  s_endpgm\n"
    parent = original.replace("  s_barrier\n", "")
    result = diagnose_candidate(original, parent, parent)
    assert not result["ok_vs_original"]
    assert any("barrier count changed" in finding["message"] for finding in result["new_findings"])
    assert result["candidate_vs_parent_findings"] == []


def test_actual_payload_moves_are_measured_not_copied_from_intent():
    spec = {"kind": "layout", "region": "loop", "layout": {0: [_loads(_SYNTH)[1][0]]},
            "opt_level": 1, "protect_prefetch": False, "strict_verify": False}
    candidate, ok = driver.build_candidate(_SYNTH, spec)
    assert ok
    result = diagnose_candidate(_SYNTH, _SYNTH, candidate, spec=spec)
    changed = result["actual_changes"]
    assert changed["declared_intent"] == spec
    assert changed["payload_changed"] and changed["payload_preserved"]
    load = next(move for move in changed["payload_moves"] if move["instruction"]["opcode"] == "buffer_load_dwordx4")
    assert load["parent_position"] == 5 and load["candidate_position"] == 1
    no_change = actual_changes(_SYNTH, _SYNTH, spec)
    assert no_change["declared_intent"] == spec
    assert not no_change["bytes_changed"] and not no_change["payload_moves"]


def test_fixup_additions_do_not_count_as_payload_moves():
    candidate = UNSYNCED.replace("  v_add", "  s_waitcnt vmcnt(0)\n  v_add")
    changed = actual_changes(UNSYNCED, candidate)
    assert changed["repair_only"] is True
    assert changed["repair_added"][0]["opcode"] == "s_waitcnt"
    assert not changed["payload_moves"] and not changed["payload_changed"]
    removed = actual_changes(candidate, UNSYNCED)
    assert removed["repair_removed"][0]["count"] == 1


def test_payload_edits_and_ambiguous_duplicate_moves_are_explicit():
    changed = actual_changes(UNSYNCED, UNSYNCED.replace("v2, v0, 1", "v3, v0, 1"))
    assert not changed["payload_preserved"]
    assert len(changed["payload_added"]) == len(changed["payload_removed"]) == 1
    source = ".text\nk:\n  s_mov_b32 s0, 1\n  s_mov_b32 s0, 1\n  s_mov_b32 s2, 3\n  s_endpgm\n"
    reordered = source.replace("  s_mov_b32 s2, 3\n", "").replace("k:\n", "k:\n  s_mov_b32 s2, 3\n")
    changed = actual_changes(source, reordered)
    assert len(changed["ambiguous_payload_matches"]) == 1
    assert all(move["instruction"]["operands"] != ["s0", "1"] for move in changed["payload_moves"])


def test_address_locations_are_removed_but_operand_constants_are_bound(monkeypatch):
    monkeypatch.setattr(diagnostics, "raw_findings", lambda source, reference:
                        ["line {}: synthetic issue at 0x{}".format(3 if source == UNSYNCED else 4,
                                                                   "1000" if source == UNSYNCED else "2000")])
    result = diagnose_candidate(UNSYNCED, UNSYNCED, "\n" + UNSYNCED)
    assert result["ok_vs_original"] is True
    assert result["inherited_findings"][0]["instructions"][0]["operands"][-1] == "1"
    assert "at <address>" in result["inherited_findings"][0]["identity"]["message"]


def test_dependency_summary_binds_endpoint_instructions_not_graph_iids(monkeypatch):
    monkeypatch.setattr(diagnostics, "raw_findings", lambda source, reference:
                        ["dep order violated: 1 edges (e.g. [(2, 3, 'raw')])"] if source == UNSYNCED else
                        ["dep order violated: 1 edges (e.g. [(3, 4, 'raw')])"])
    result = diagnose_candidate(UNSYNCED, UNSYNCED, "\n" + UNSYNCED)
    assert result["ok_vs_original"] is True
    edge = result["inherited_findings"][0]["identity"]["edges"][0]
    assert edge["from"]["opcode"] == "buffer_load_dword"
    assert edge["to"]["opcode"] == "v_add_u32"


def test_truncated_dependency_summary_cannot_expand_warning_waiver(monkeypatch):
    monkeypatch.setattr(diagnostics, "raw_findings", lambda source, reference:
                        ["dep order violated: 4 edges (e.g. [(2, 3, 'raw')])"])
    result = diagnose_candidate(UNSYNCED, UNSYNCED, UNSYNCED + "// change\n")
    assert not result["ok_vs_original"]
    assert result["new_findings"][0]["summary_complete"] is False


def test_strict_flag_requires_boolean():
    with pytest.raises(ValueError, match="boolean"):
        diagnose_candidate(UNSYNCED, UNSYNCED, UNSYNCED, strict_verify=1)
