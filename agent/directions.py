"""Bounded CPU suggestions and frozen search-budget policy normalization.

Directions are experiment categories, not performance verdicts. This module
does not evaluate/profile, read learned priors, spend budgets, or change run
state. The controller still binds observations and adjudicates every proposal.
"""
from __future__ import annotations

from bisect import bisect_left
import hashlib
from itertools import zip_longest

from agent.session import AgentSession
from reorder.model import Kind
from search import driver


MAX_POLICY_INTEGER = 2 ** 53 - 1  # preserve exact JSON numbers through the SDK
MAX_SUGGESTIONS = 32
_DEFAULT_POLICY = {
    "direction_eval_call_limit": None,
    "profile_call_limit": 0,
    "stagnation_limit": None,
    "reuse_proposal_limit": None,
    "reuse_eval_call_limit": None,
    "independent_eval_reserve": 0,
}


def validate_search_policy(value=None):
    """Return an independent complete policy suitable for a frozen manifest.

    Missing optional limits default to None (unlimited); explicit zero permits
    no calls/proposals in that category. Stagnation, when enabled, is positive.
    Profiling defaults to zero and needs an explicit opt-in (positive or None).
    The independent reserve is always an integer; cross-checking it against the
    total/final budgets belongs to the controller that owns those budgets.
    """
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - set(_DEFAULT_POLICY):
        raise ValueError("search policy must contain only supported budget fields")
    result = dict(_DEFAULT_POLICY, **value)
    for key, limit in result.items():
        if limit is None and key != "independent_eval_reserve":
            continue
        minimum = 1 if key == "stagnation_limit" else 0
        if type(limit) is not int or not minimum <= limit <= MAX_POLICY_INTEGER:
            raise ValueError("invalid search policy " + key)
    return result


def _build_policy(value):
    if (not isinstance(value, dict) or
            set(value) != {"opt_level", "protect_prefetch", "strict_verify"} or
            type(value["opt_level"]) is not int or value["opt_level"] != 1 or
            type(value["protect_prefetch"]) is not bool or
            type(value["strict_verify"]) is not bool):
        raise ValueError("suggestions require the complete frozen L1 build policy")
    return dict(value)


def _interleave(groups):
    """Give distinct available directions a turn before local alternatives."""
    for entries in zip_longest(*groups):
        for entry in entries:
            if entry is not None:
                yield entry


def _layout_intents(editor, anchors, region):
    positions = {iid: pos for pos, iid in enumerate(editor.order)}
    anchor_positions = [positions[iid] for iid in anchors]
    last_slot = len(anchors) - 2
    kinds = (("memory", {Kind.VMEM_LOAD, Kind.DS_READ, Kind.SMEM}),
             ("alu", {Kind.VALU, Kind.SALU}))

    def group(name, selected, early):
        # A one-instruction request keeps each experiment small. Independence,
        # bundle movement, fences and prefetch protection are decided by propose.
        count = 0
        for iid in editor.order:
            if iid in editor._fences or editor.kind_of(iid) not in selected:
                continue
            count += 1
            if count > 16:
                break
            current_slot = bisect_left(anchor_positions, positions[iid]) - 1
            if early:
                nearest = min(last_slot, current_slot - 1)
                slots = [nearest, 0] if nearest >= 0 else []
            else:
                nearest = max(0, current_slot + 1)
                slots = [nearest, last_slot] if nearest <= last_slot else []
            # Slot coordinates come from actual MFMA anchors, never from a
            # legal_window (which contains instruction positions, not slots).
            for slot in dict.fromkeys(slots):
                direction = name + ("_early" if early else "_late")
                yield {"direction": direction,
                       "spec": {"kind": "layout", "region": region,
                                "layout": {str(slot): [iid]}},
                       "hypothesis": "Move one {} instruction to an {} anchor gap; "
                                     "test its effect on measured scheduling stalls.".format(
                                         name, "earlier" if early else "later")}

    return _interleave([group(name, selected, early)
                        for name, selected in kinds for early in (True, False)])


def _order_intents(session, editor, region):
    positions = {iid: pos for pos, iid in enumerate(editor.order)}
    suggested = session.suggest_orders(n=3)["candidates"]

    def group(candidate):
        order = candidate["order"]
        for previous, iid in zip(order, order[1:]):
            if iid in editor._fences or positions[iid] == positions[previous] + 1:
                continue
            # Use the scheduler's desired adjacency as a two-IID local intent.
            # Do not submit an unbounded full-region order or assume a local
            # move inherits the complete schedule's legality; propose checks it.
            yield {"direction": candidate["weights"],
                   "spec": {"kind": "order", "region": region, "order": [previous, iid]},
                   "hypothesis": "Try a local adjacency from the {} scheduler preset; "
                                 "test whether the new order improves measured performance.".format(
                                     candidate["weights"])}

    return _interleave([group(candidate) for candidate in suggested])


def suggestions(source, region, build_policy, n=6):
    """Return at most n unique, statically checked layout/order experiment specs.

    Every spec passes the same non-committing propose gate as run.prepare, with
    no skipped placements, and is materialized under the supplied frozen policy.
    Materialized bytes are deduplicated against source, normalization and earlier
    suggestions. Static acceptance retains build_candidate's existing treatment
    of seed warnings; it is not a semantic or GPU correctness proof.

    The returned spec intentionally excludes policy fields so it can be passed
    unchanged to run.prepare alongside a current observation ID/source digest.
    Suggestions do not themselves create observations or charge proposal budget.
    """
    policy = _build_policy(build_policy)
    if not isinstance(source, str) or not source.strip():
        raise ValueError("suggestions require nonempty assembly source")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("suggestions require an explicit region")
    if type(n) is not int or not 0 <= n <= MAX_SUGGESTIONS:
        raise ValueError("suggestion count must be between 0 and {}".format(MAX_SUGGESTIONS))
    if n == 0:
        return []
    session = AgentSession(source, None, region=region,
                           protect_prefetch=policy["protect_prefetch"])
    editor = session._editor()
    anchors = editor.anchors(Kind.MFMA)
    if len(anchors) == 1:
        return []  # no bounded inter-anchor slot; do not move the lone anchor
    intents = (_layout_intents(editor, anchors, region) if anchors else
               _order_intents(session, editor, region))
    digest = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
    seen = {digest(source)}
    normalized, ok = driver.build_candidate(source, dict(policy, kind="ladder", level=1, region=region))
    if ok:
        seen.add(digest(normalized))
    out = []
    for attempt, entry in enumerate(intents):
        if attempt >= min(96, max(12, 8 * n)):
            break
        spec = entry["spec"]
        if spec["kind"] == "layout":
            report = session.propose([{int(k): v for k, v in spec["layout"].items()}])[0]
            legal, skipped = report.legal, report.skipped
        else:
            report = session.propose_orders([spec["order"]])[0]
            legal, skipped = report["legal"], report.get("skipped")
        if not legal or skipped:
            continue
        candidate, ok = driver.build_candidate(source, dict(spec, **policy))
        identity = digest(candidate)
        if not ok or identity in seen:
            continue
        seen.add(identity)
        out.append(entry)
        if len(out) >= n:
            break
    return out
