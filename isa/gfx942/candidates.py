"""Bounded scheduling hypotheses from current instructions, never saved IIDs.

These generators do not adjudicate legality or predict timing. Every complete
intent must pass the ordinary propose/materialize gates and client evaluation.
"""
from bisect import bisect_left
from collections import defaultdict
from itertools import zip_longest

from reorder.model import Kind

MAX_CHAIN = 12
MAX_REPEATS = 12
MAX_MOVED = 96
SHIFTS = (1, 2, 3)


def _geometry(editor, anchors):
    positions = {iid: i for i, iid in enumerate(editor.order)}
    anchor_positions = [positions[i] for i in anchors]
    slots = {iid: bisect_left(anchor_positions, positions[iid]) - 1 for iid in editor.order}
    blocks, block, local_anchors = {}, 0, defaultdict(list)
    for iid in editor.order:
        if iid in editor._fences:
            block += 1
        blocks[iid] = block
        if iid in anchors:
            local_anchors[block].append(iid)
    return positions, slots, blocks, local_anchors


def _chain_intervals(editor, run):
    # Connected RAW components include implicit SCC carry/compare consumers.
    # Overlapping intervals merge so no independent interleaved instruction is
    # silently reordered inside a proposed contiguous chain.
    parent = list(range(len(run)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    definitions = {}
    for i, iid in enumerate(run):
        line = editor._line_of[iid]
        defs, uses = editor.target.def_use(line.opcode, line.operands)
        for unit in uses:
            if unit in definitions:
                parent[root(i)] = root(definitions[unit])
        for unit in defs:
            definitions[unit] = i
    groups = defaultdict(list)
    for i in range(len(run)):
        groups[root(i)].append(i)
    intervals = sorted((min(g), max(g)) for g in groups.values())
    merged = []
    for lo, hi in intervals:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    for lo, hi in merged:
        chain = run[lo:hi + 1]
        if 2 <= len(chain) <= MAX_CHAIN and all(set(editor.unit(i)) <= set(chain) for i in chain):
            yield chain


def _chains(editor):
    run = []
    for iid in editor.order:
        if editor.kind_of(iid) is Kind.SALU and iid not in editor._fences:
            run.append(iid)
        else:
            yield from _chain_intervals(editor, run)
            run = []
    yield from _chain_intervals(editor, run)


def _placement(editor, anchors, geometry, members, shift):
    positions, slots, blocks, _ = geometry
    if not members or any(i in editor._fences for i in members):
        return None
    source_slot = slots[members[0]]
    target = source_slot - shift
    if not 0 <= target < len(anchors) - 1:
        return None
    # Never propose crossing a fence/basic-block boundary. The engine still
    # checks register, SCC, bundle, memory, wait and prefetch dependencies.
    block = blocks[members[0]]
    if any(blocks[i] != block for i in members + [anchors[target], anchors[target + 1]]):
        return None
    if any(positions[i] <= positions[anchors[target + 1]] for i in members):
        return None
    return {"iids": list(members), "source_slot": source_slot, "target_slot": target, "block": block}


def _intent(region, direction, placements, hypothesis):
    layout = defaultdict(list)
    for item in placements:
        layout[str(item["target_slot"])].extend(item.get("request_iids", item["iids"]))
    if sum(len(p["iids"]) for p in placements) > MAX_MOVED:
        return None
    return {"direction": direction, "spec": {"kind": "layout", "region": region, "layout": dict(layout)},
            "hypothesis": hypothesis, "details": {"placements": placements,
                "scope": "current fence-separated blocks; complete intent requires engine validation",
                "timing_prediction": None}}


def salu_chains(editor, anchors, region):
    if len(anchors) < 2:
        return
    geometry = _geometry(editor, anchors)
    # Interleave positions across all blocks; avoid exhausting the trial budget
    # on only the first unfolded stage or the first shift distance.
    by_block = defaultdict(list)
    for members in _chains(editor):
        by_block[geometry[2][members[0]]].append(members)
    chains = [chain for group in zip_longest(*by_block.values()) for chain in group if chain]
    for shift in SHIFTS:
        for members in chains:
            item = _placement(editor, anchors, geometry, members, shift)
            if item:
                yield _intent(region, "salu_chain_overlap", [item],
                    "Move a complete contiguous RAW/SCC scalar chain into an earlier MFMA gap; test scalar overlap without assuming an ordinary VALU release window.")


def _repeat_key(editor, anchors, geometry, members):
    _, slots, blocks, local = geometry
    block = blocks[members[0]]
    if not local[block]:
        return None
    first_slot = slots[local[block][0]] + 1
    return (tuple(editor.opcode_of(i) for i in members), slots[members[0]] - first_slot, len(local[block]))


def repeated_salu_chains(editor, anchors, region):
    if len(anchors) < 2:
        return
    geometry = _geometry(editor, anchors)
    _, slots, blocks, _ = geometry
    # Group structurally matching chains by stage-local gap and ordinal. IIDs,
    # register numbers, absolute offsets and stage strides are never copied.
    groups, ordinals, clusters = defaultdict(list), defaultdict(int), defaultdict(list)
    for members in _chains(editor):
        key = _repeat_key(editor, anchors, geometry, members)
        if key is None:
            continue
        block = blocks[members[0]]
        ordinal = ordinals[(block, key)]
        ordinals[(block, key)] += 1
        groups[(key, ordinal)].append(members)
        clusters[(block, slots[members[0]], key)].append(members)
    # Spread a prefix of clustered chains over distinct earlier gaps. This
    # expresses the reviewed mask-chain strategy without kernel-specific IDs.
    spread = defaultdict(list)
    for (block, slot, key), chains in clusters.items():
        for width in range(2, min(3, len(chains)) + 1):
            spread[(key, width)].append(chains[:width])
    for (_, width), stages in spread.items():
        if len(stages) < 2:
            continue
        placements = [_placement(editor, anchors, geometry, chain, width - i)
                      for chains in stages[:MAX_REPEATS] for i, chain in enumerate(chains)]
        if all(placements):
            item = _intent(region, "repeated_salu_spread", placements,
                "Spread complete scalar chains from a crowded gap across earlier MFMA gaps in matching stages; test the aggregate effect with unchanged scalar-chain order.")
            if item:
                yield item
    for shift in SHIFTS:
        for members in groups.values():
            if len(members) < 2:
                continue
            placements = [_placement(editor, anchors, geometry, chain, shift) for chain in members[:MAX_REPEATS]]
            if all(placements):
                item = _intent(region, "repeated_salu_overlap", placements,
                    "Move matching RAW/SCC chains earlier in multiple fence-separated stages; test repeated scalar overlap, with every occurrence independently checked by the engine.")
                if item:
                    yield item


def repeated_operand_prefetch(editor, anchors, region):
    if len(anchors) < 2:
        return
    geometry = _geometry(editor, anchors)
    positions, _, blocks, _ = geometry
    groups, ordinals, seen = defaultdict(list), defaultdict(int), set()
    for iid in editor.order:
        if editor.kind_of(iid) not in (Kind.VMEM_LOAD, Kind.DS_READ, Kind.SMEM):
            continue
        members = sorted(editor.unit(iid), key=positions.__getitem__)
        if tuple(members) in seen:
            continue
        seen.add(tuple(members))
        key = _repeat_key(editor, anchors, geometry, members)
        if key is None:
            continue
        block = blocks[members[0]]
        ordinal = ordinals[(block, key)]
        ordinals[(block, key)] += 1
        groups[(key, ordinal)].append(members)
    for shift in (1, 2):
        for members in groups.values():
            if len(members) < 2:
                continue
            placements = [_placement(editor, anchors, geometry, unit, shift) for unit in members[:MAX_REPEATS]]
            if all(placements):
                for placement in placements:
                    # The editor moves an m0 bundle atomically. Request its
                    # leader once, retaining all members in the audit details.
                    placement["request_iids"] = [placement["iids"][0]]
                item = _intent(region, "repeated_operand_prefetch", placements,
                    "Advance matching operand-load units in repeated stages; test latency overlap while preserving engine memory, wait, m0-bundle and prefetch constraints.")
                if item:
                    yield item
