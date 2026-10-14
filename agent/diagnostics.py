"""Verifier evidence and observed assembly changes, without ISA rule changes.

Finding identities omit source locations, but preserve operand constants and
hazard quantities. Only the original snapshot supplies warning allowances.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import copy
import hashlib
import json
import re

from reorder import parser, regions
from reorder.model import Kind, LineKind
from reorder.verifier import Verifier
from search import driver


SCHEMA_VERSION = 1
_LINE = re.compile(r"\bline\s+(\d+)\b")
_ADDRESS = re.compile(r"\b(address|addr|pc|at)\s*[:=]?\s*0x[0-9a-fA-F]+\b")
_DEP = re.compile(r"^dep order violated: (\d+) edges \(e\.g\. (.*)\)$")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _sha(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def raw_findings(source, reference):
    """Execute the complete existing checker, including Target invariants.

    Matches the final check in search.driver.build_candidate: fresh parse,
    target selection, complete region analysis and an explicit reference.
    No fixup pass runs here; diagnostics describe the supplied bytes.
    """
    program = parser.parse(source)
    target = driver._default_target(program)
    result = Verifier(target, reference=parser.parse(reference),
                      analysis=regions.analyze(program, target)).verify(program)
    return sorted(result.violations)


def _instructions(source):
    program = parser.parse(source)
    target = driver._default_target(program)
    label, rows = None, []
    for item in regions._collect_code_items(program):
        line = item.line
        if line.kind is LineKind.LABEL:
            label = line.label
        elif line.kind is LineKind.INSTR:
            kind = target.classify(line.opcode or "", line.operands)
            rows.append({"line_index": line.idx, "label": label, "opcode": line.opcode,
                         "operands": list(line.operands), "raw": line.raw,
                         "repair": kind in (Kind.WAITCNT, Kind.NOP) or driver._is_hazard_line(line)})
    return rows


def _instruction_key(row):
    return {"label": row["label"], "opcode": row["opcode"], "operands": row["operands"]}


def _finding_type(message):
    if message.startswith("dep order violated:"):
        return "dependency_order"
    if "LDS round-trip not synced" in message:
        return "lds_roundtrip"
    if "barrier LDS-release fence missing" in message:
        return "barrier_release"
    if "not synced" in message:
        return "unsynchronized_use"
    return "target_invariant"


def _structured_findings(source, reference):
    instructions = _instructions(source)
    by_line = {row["line_index"]: row for row in instructions}
    multiplicities = Counter(_digest(_instruction_key(row)) for row in instructions)
    findings = []
    for message in raw_findings(source, reference):
        locations = [int(value) for value in _LINE.findall(message)]
        normalized = _ADDRESS.sub(lambda match: match.group(1) + " <address>",
                                  _LINE.sub("line <instruction>", message))
        dependency = _DEP.fullmatch(message)
        edges, complete = [], True
        if dependency:
            # Existing checker returns a count and at most three edge examples.
            # Preserve every available operand/edge type instead of hashing
            # unstable graph IIDs; truncated summaries cannot gain new waivers.
            try:
                raw_edges = ast.literal_eval(dependency.group(2))
                if not isinstance(raw_edges, list) or any(
                        not isinstance(e, tuple) or len(e) != 3 or
                        type(e[0]) is not int or type(e[1]) is not int or not isinstance(e[2], str)
                        for e in raw_edges):
                    raise ValueError("invalid dependency summary")
                locations = [iid for edge in raw_edges for iid in edge[:2]]
                for start, end, kind in raw_edges:
                    edges.append({"from": _instruction_key(by_line[start]) if start in by_line else None,
                                  "to": _instruction_key(by_line[end]) if end in by_line else None,
                                  "type": kind})
                edges.sort(key=_digest)
                complete = len(raw_edges) == int(dependency.group(1))
                normalized = "dep order violated: {} edges".format(dependency.group(1))
            except (ValueError, SyntaxError):
                complete = False
        identities = [_instruction_key(by_line[i]) if i in by_line else {"unresolved_instruction": True}
                      for i in locations]
        # Each reference keeps its semantic role/order for multi-line findings.
        # Dependency endpoints are already named and ordered in `edges`.
        identity = {"type": _finding_type(message), "message": normalized,
                    "instructions": [] if edges else identities, "edges": edges}
        ambiguous = (not complete or any(i not in by_line for i in locations) or
                     any(multiplicities[_digest(_instruction_key(by_line[i]))] != 1
                         for i in locations if i in by_line))
        findings.append({"id": _digest(identity), "type": identity["type"], "identity": identity,
                         "message": message, "line_indices": locations, "instructions": identities,
                         "identity_ambiguous": ambiguous, "summary_complete": complete})
    return {"sha256": _sha(source), "reference_sha256": _sha(reference),
            "verifier_ok": not findings, "findings": findings}


def _compare(original, snapshot):
    remaining = defaultdict(list)
    for finding in original["findings"]:
        remaining[finding["id"]].append(finding)
    inherited, new = [], []
    for finding in snapshot["findings"]:
        matches = remaining[finding["id"]]
        unique = not finding["identity_ambiguous"] and matches and not matches[0]["identity_ambiguous"]
        if matches and (unique or original["sha256"] == snapshot["sha256"]):
            matches.pop(0)
            inherited.append(finding)
        else:
            new.append(finding)
    # Absence of a finding identity is a resolved diagnostic, not a semantic
    # proof of a bug fix. Ambiguous possible matches are not called resolved.
    present = {finding["id"] for finding in snapshot["findings"]}
    resolved = [finding for key, findings in remaining.items() if key not in present for finding in findings]
    uncertain = [finding for key, findings in remaining.items() if key in present for finding in findings]
    return {"new_findings": new, "inherited_findings": inherited, "resolved_findings": resolved,
            "unmatched_original_findings": uncertain, "ok_vs_original": not new}


def _raw_key(row):
    return row["label"], row["raw"]


def _delta_rows(before, after):
    old = Counter(_raw_key(row) for row in before)
    new = Counter(_raw_key(row) for row in after)
    examples = {_raw_key(row): row for row in before + after}
    def rows(counts):
        return [dict(copy.deepcopy(examples[key]), count=count)
                for key, count in sorted(counts.items(), key=lambda pair: repr(pair[0]))]
    return rows(new - old), rows(old - new)


def actual_changes(parent_src, candidate_src, spec=None):
    """Compare materialized bytes; never infer success from a declared intent.

    Payload positions exclude engine-owned repair lines. Repeated exact text
    is reported as ambiguous rather than assigned an invented movement.
    """
    before, after = _instructions(parent_src), _instructions(candidate_src)
    old_payload = [row for row in before if not row["repair"]]
    new_payload = [row for row in after if not row["repair"]]
    payload_added, payload_removed = _delta_rows(old_payload, new_payload)
    repair_added, repair_removed = _delta_rows([row for row in before if row["repair"]],
                                               [row for row in after if row["repair"]])
    old_positions, new_positions = defaultdict(list), defaultdict(list)
    for index, row in enumerate(old_payload):
        old_positions[_raw_key(row)].append((index, row))
    for index, row in enumerate(new_payload):
        new_positions[_raw_key(row)].append((index, row))
    moves, ambiguous = [], []
    for key in sorted(set(old_positions) & set(new_positions), key=repr):
        old, new = old_positions[key], new_positions[key]
        if len(old) != 1 or len(new) != 1:
            ambiguous.append({"label": key[0], "raw": key[1],
                              "parent_positions": [item[0] for item in old],
                              "candidate_positions": [item[0] for item in new]})
        elif old[0][0] != new[0][0]:
            moves.append({"instruction": _instruction_key(old[0][1]), "raw": key[1],
                          "parent_position": old[0][0], "candidate_position": new[0][0],
                          "parent_line_index": old[0][1]["line_index"],
                          "candidate_line_index": new[0][1]["line_index"]})
    payload_changed = [_raw_key(row) for row in old_payload] != [_raw_key(row) for row in new_payload]
    repairs_changed = bool(repair_added or repair_removed)
    non_instruction = lambda source: [line.raw for line in parser.parse(source).lines
                                     if line.kind is not LineKind.INSTR]
    other_changed = non_instruction(parent_src) != non_instruction(candidate_src)
    return {"parent_sha256": _sha(parent_src), "candidate_sha256": _sha(candidate_src),
            "declared_intent": copy.deepcopy(spec), "bytes_changed": parent_src != candidate_src,
            "payload_changed": payload_changed, "payload_preserved": not payload_added and not payload_removed,
            "payload_moves": moves, "ambiguous_payload_matches": ambiguous,
            "payload_added": payload_added, "payload_removed": payload_removed,
            "repair_added": repair_added, "repair_removed": repair_removed,
            "non_instruction_bytes_changed": other_changed,
            "repair_only": parent_src != candidate_src and not payload_changed and repairs_changed and not other_changed}


def diagnose_candidate(original_src, parent_src, candidate_src, *, spec=None, strict_verify=False):
    """Return JSON evidence and a fixed-original warning decision.

    The original is always checked against itself; both later versions are
    checked against original (including reference-sensitive invariants). The
    candidate is additionally checked against parent, as build_candidate does.
    A parent warning never enlarges the original allowance. `ok_vs_original`
    cannot override build_candidate/propose failure or client correctness.
    """
    if type(strict_verify) is not bool:
        raise ValueError("strict_verify must be a boolean")
    original = _structured_findings(original_src, original_src)
    parent = _structured_findings(parent_src, original_src)
    candidate = _structured_findings(candidate_src, original_src)
    compared = _compare(original, candidate)
    parent_compared = _compare(original, parent)
    if strict_verify:
        compared["ok_vs_original"] = not candidate["findings"]
    return dict(compared, schema_version=SCHEMA_VERSION, original=original, parent=parent,
                candidate=candidate, strict_verify=strict_verify,
                parent_new_findings=parent_compared["new_findings"],
                candidate_vs_parent_findings=raw_findings(candidate_src, parent_src),
                actual_changes=actual_changes(parent_src, candidate_src, spec),
                allowance_source_sha256=original["sha256"],
                scope="existing_static_verifier; no_semantic_equivalence_or_hardware_correctness_claim")
