"""CPU-only replay of constrained intents with explicit, reproducible ancestry.

No assembly patches or caller-supplied descendant text are accepted. Repeated
instructions that lack a unique exact identity are deliberately not guessed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import re

from agent.session import AgentSession
from agent.diagnostics import raw_findings
from reorder import parser
from reorder.model import Kind, LineKind
from search import driver


class ReplayError(ValueError):
    def __init__(self, code, message, diagnostics=None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


def source_sha256(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _policy(policy):
    required = {"opt_level", "protect_prefetch", "strict_verify"}
    if (not isinstance(policy, dict) or set(policy) != required or
            type(policy.get("opt_level")) is not int or policy["opt_level"] != 1 or
            type(policy.get("protect_prefetch")) is not bool or
            type(policy.get("strict_verify")) is not bool):
        raise ReplayError("policy_mismatch", "replay requires the complete supported L1 build policy")
    return copy.deepcopy(policy)


def _spec(spec, policy, normalization=False):
    if not isinstance(spec, dict):
        raise ReplayError("invalid_spec", "spec must be an object")
    spec = copy.deepcopy(spec)
    kind = spec.get("kind")
    allowed = {"kind", "region", kind} | set(policy) if isinstance(kind, str) else set()
    if normalization and kind == "ladder":
        allowed = {"kind", "region", "level"} | set(policy)
        if type(spec.get("level")) is not int or spec["level"] != 1:
            raise ReplayError("invalid_spec", "only the initial L1 normalization may be replayed")
    elif kind not in ("layout", "order"):
        raise ReplayError("invalid_spec", "only layout/order intents may be replayed")
    if set(spec) - allowed or not isinstance(spec.get("region"), str) or not spec["region"]:
        raise ReplayError("invalid_spec", "spec requires an explicit region and supported fields")
    if any(k in spec and (type(spec[k]) is not type(v) or spec[k] != v) for k, v in policy.items()):
        raise ReplayError("policy_mismatch", "spec changes the frozen build policy")
    if kind == "layout":
        value = spec.get("layout")
        if not isinstance(value, dict):
            raise ReplayError("invalid_spec", "layout must be a slot object")
        layout = {}
        for slot, ids in value.items():
            if not ((type(slot) is int and slot >= 0) or
                    (isinstance(slot, str) and re.fullmatch(r"0|[1-9][0-9]*", slot))):
                raise ReplayError("invalid_spec", "layout slots must be canonical nonnegative integers")
            if str(slot) in layout:
                raise ReplayError("invalid_spec", "duplicate layout slot")
            layout[str(slot)] = ids
        spec["layout"] = layout
        sequences = list(layout.values())
    else:
        sequences = [spec.get("order")] if kind == "order" else []
    if any(not isinstance(ids, list) or any(type(i) is not int or i < 0 for i in ids)
           for ids in sequences):
        raise ReplayError("invalid_spec", "instruction IDs must be nonnegative integer lists")
    ids = [i for seq in sequences for i in seq]
    if len(ids) != len(set(ids)):
        raise ReplayError("invalid_spec", "duplicate instruction IDs")
    spec.update(policy)
    return spec


def _session(source, spec):
    return AgentSession(source, None, region=spec["region"],
                        protect_prefetch=spec["protect_prefetch"])


def _propose(source, spec):
    session = _session(source, spec)
    editor = session._editor()
    ids = spec["order"] if spec["kind"] == "order" else [i for row in spec["layout"].values() for i in row]
    if any(i not in editor._line_of for i in ids):
        raise ReplayError("invalid_spec", "intent refers to instructions outside the selected region")
    if spec["kind"] == "layout":
        report = session.propose([{int(k): v for k, v in spec["layout"].items()}])[0]
        report = {"legal": report.legal, "placed": report.placed, "skipped": report.skipped}
    else:
        report = session.propose_orders([spec["order"]])[0]
    if not report["legal"] or report.get("skipped"):
        raise ReplayError("proposal_rejected", "replay has illegal or skipped placements", report)
    return report


def _findings(source, original):
    return sorted(set(raw_findings(source, original)))


def _build(source, spec, original, original_findings):
    report = None if spec["kind"] == "ladder" else _propose(source, spec)
    candidate, ok = driver.build_candidate(source, spec)
    if not ok:
        raise ReplayError("verify_failed", "replayed candidate failed build verification")
    findings = _findings(candidate, original)
    new = sorted(set(findings) - set(original_findings))
    diagnostics = {"original_findings": original_findings, "candidate_findings": findings,
                   "new_findings": new, "report": report}
    if new or (spec["strict_verify"] and findings):
        raise ReplayError("new_static_findings", "replay exceeds the original warning allowance", diagnostics)
    return candidate, diagnostics


def verify_chain(original_src, chain, build_policy):
    """Rebuild a chain from original bytes and verify every recorded SHA.

    Each step has ``spec``, ``source_sha256`` and ``candidate_sha256``. Only
    the first step may be the controller's explicit ladder/L1 normalization.
    Returns the final source, canonical chain, and per-step diagnostics. It
    never imports measurements, mutates a run, or invokes an evaluator.
    """
    policy = _policy(build_policy)
    if not isinstance(chain, list):
        raise ReplayError("invalid_chain", "chain must be a list")
    source, checked = original_src, []
    allowance = _findings(original_src, original_src)
    for index, step in enumerate(chain):
        if not isinstance(step, dict) or set(step) != {"spec", "source_sha256", "candidate_sha256"}:
            raise ReplayError("invalid_chain", "chain steps require spec and both source/result hashes")
        if step["source_sha256"] != source_sha256(source):
            raise ReplayError("ancestry_mismatch", "chain does not descend from the supplied original")
        spec = _spec(step["spec"], policy, normalization=index == 0)
        candidate, diagnostics = _build(source, spec, original_src, allowance)
        if step["candidate_sha256"] != source_sha256(candidate):
            raise ReplayError("artifact_mismatch", "recorded candidate is not reproduced by its intent")
        checked.append({"spec": spec, "source_sha256": source_sha256(source),
                        "candidate_sha256": source_sha256(candidate),
                        "source": source, "diagnostics": diagnostics})
        source = candidate
    return {"original_sha256": source_sha256(original_src), "source": source,
            "sha256": source_sha256(source), "steps": checked}


def _view(source, spec):
    editor = _session(source, spec)._editor()
    program, region = editor.program, editor.region
    # Nearest label is invariant under legal within-block reordering. Include
    # the complete label sequence to fail closed if a selector changed scope.
    label = None
    keys = {}
    for line in program.lines:
        if line.kind is LineKind.LABEL:
            label = line.raw
        elif line.idx in editor._line_of:
            keys[line.idx] = (label, line.raw)
    labels = [ln.raw for ln in program.lines
              if ln.kind is LineKind.LABEL and region.line_start <= ln.idx <= region.line_end]
    # Existing engine passes own waits/nops/MSB rematerialization. They may
    # change these lines while preserving the region's payload membership.
    # Referenced repair lines still require an exact unique match below.
    payload = [key for iid, key in keys.items()
               if editor.kind_of(iid) not in (Kind.WAITCNT, Kind.NOP) and
               not driver._is_hazard_line(editor._line_of[iid])]
    identity = (region.kind.value, region.header_label, region.outlined, labels, Counter(payload))
    return editor, keys, identity


def remap_spec(source, target, spec, build_policy):
    """Map exact instruction identities within an unchanged selected scope.

    Full raw instruction text plus its preceding label must be unique in both
    versions. No opcode-only, line-number, fuzzy, or repeated-occurrence match
    is attempted. A byte-identical parent uses its already-bound IIDs.
    """
    spec = _spec(spec, _policy(build_policy))
    from isa import registry
    def target_identity(text):
        return (registry.arch_of_source(text),
                [line.raw.strip() for line in parser.parse(text).lines
                 if line.directive == ".amdgcn_target"])
    if target_identity(source) != target_identity(target):
        raise ReplayError("target_mismatch", "architecture or declared target features changed")
    old, old_keys, old_region = _view(source, spec)
    new, new_keys, new_region = _view(target, spec)
    if old_region != new_region:
        raise ReplayError("region_mismatch", "selected region membership or instruction text changed")
    old_anchors, new_anchors = old.anchors(Kind.MFMA), new.anchors(Kind.MFMA)
    needed = list(spec["order"]) if spec["kind"] == "order" else [
        i for ids in spec["layout"].values() for i in ids]
    if spec["kind"] == "layout":
        for slot in spec["layout"]:
            if int(slot) >= len(old_anchors):
                raise ReplayError("invalid_spec", "layout anchor slot is outside the selected region")
        needed += old_anchors
    if any(i not in old_keys for i in needed):
        raise ReplayError("invalid_spec", "intent refers to instructions outside the selected region")
    old_groups, new_groups = defaultdict(list), defaultdict(list)
    for iid, key in old_keys.items():
        old_groups[key].append(iid)
    for iid, key in new_keys.items():
        new_groups[key].append(iid)
    mapping = {}
    for iid in needed:
        key = old_keys[iid]
        if source == target:
            mapping[iid] = iid
        elif len(old_groups[key]) == len(new_groups[key]) == 1:
            mapping[iid] = new_groups[key][0]
        else:
            raise ReplayError("ambiguous_identity", "instruction identity is not unique; observe and propose again",
                              {"iid": iid, "raw": key[1]})
    actual = copy.deepcopy(spec)
    if spec["kind"] == "order":
        actual["order"] = [mapping[i] for i in spec["order"]]
    else:
        if [mapping[i] for i in old_anchors] != new_anchors:
            raise ReplayError("anchor_conflict", "anchor order changed; layout gaps no longer match")
        actual["layout"] = {k: [mapping[i] for i in ids] for k, ids in spec["layout"].items()}
    return {"spec": actual, "mapping": {str(k): v for k, v in mapping.items()},
            "identity_method": "exact_parent" if source == target else "unique_label_and_raw_instruction"}


def _retained(source, candidate, spec, policy):
    actual = remap_spec(source, candidate, spec, policy)["spec"]
    editor = _session(candidate, actual)._editor()
    pos = {iid: index for index, iid in enumerate(editor.order)}
    if actual["kind"] == "order":
        positions = [pos[i] for i in actual["order"]]
        retained = positions == sorted(positions)
    else:
        anchors = editor.anchors(Kind.MFMA)
        retained = True
        for slot, ids in actual["layout"].items():
            slot = int(slot)
            positions = [pos[anchors[slot]]] + [pos[i] for i in ids]
            if slot + 1 < len(anchors):
                positions.append(pos[anchors[slot + 1]])
            retained = retained and positions == sorted(positions) and len(set(positions)) == len(positions)
    if not retained:
        raise ReplayError("intent_conflict", "combination does not retain a recorded intent")


def replay_intent(original_src, source_chain, target_chain, spec, build_policy):
    """Replay one source-parent intent onto a sibling/descendant target parent.

    Both parents are independently rebuilt from the exact same original.
    Existing target-chain intents must still hold after combination; conflicts
    and ambiguous identities fail closed. Successful output is an unmeasured
    candidate, never a promoted incumbent or an imported performance result.
    """
    policy = _policy(build_policy)
    source = verify_chain(original_src, source_chain, policy)
    target = verify_chain(original_src, target_chain, policy)
    spec = _spec(spec, policy)
    # Validate the archived intent on its actual parent, not just the mapping.
    _propose(source["source"], spec)
    mapped = remap_spec(source["source"], target["source"], spec, policy)
    candidate, diagnostics = _build(target["source"], mapped["spec"], original_src,
                                    _findings(original_src, original_src))
    _retained(target["source"], candidate, mapped["spec"], policy)
    for step in target["steps"]:
        if step["spec"]["kind"] != "ladder":
            _retained(step["source"], candidate, step["spec"], policy)
    return dict(mapped, source=candidate, source_sha256=target["sha256"],
                candidate_sha256=source_sha256(candidate), original_sha256=source["original_sha256"],
                diagnostics=diagnostics, requires_evaluation=True)
