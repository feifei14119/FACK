"""Mechanism B: declarative per-position move-DSL (the surface the AI drives).

The AI never emits ASM text; it emits a list of moves over STABLE instruction
handles, and the fixed logic (RegionEditor) validates + applies them, leaving
waitcnt recompute to the FixupPass pipeline. This module is the compiler from a
move-list (plain Python / JSON) into RegionEditor primitives, plus a stable,
kernel-agnostic addressing scheme so a move can name an instruction without
knowing its line number.

Stable handles (resolved against the editor's CURRENT order):
  ``mfma#2``            the 3rd MFMA (0-based) -- the canonical gap anchors
  ``ds_read#0``         the 1st ds_read of the region
  ``vmem_load@v4``      the vmem_load whose operands mention register ``v4``
                        (semantic anchor: "the load writing v[4:7]")
  ``ds_read@a48``       the ds_read producing/consuming ``a[48:...]``
  ``#1234``             escape hatch: the raw instruction id (line index)

Move ops (each a dict):
  {"op": "hoist", "target": H, "after": H}      move target(s) to just after anchor
  {"op": "sink",  "target": H, "before": H}     move target(s) to just before anchor
  {"op": "swap",  "a": H, "b": H}
  {"op": "layout", "slots": {0: [H, H], 2: [H]}} per-slot fillers into MFMA gaps
  {"op": "keep",  ...}                           documentation no-op

``target`` may be a single handle or a list (a list after one anchor reproduces
"put N fillers in this one gap", i.e. the heterogeneous 1/0/3 placement).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union

from reorder.editor import RegionEditor
from reorder.model import Kind

Handle = Union[str, int]

# kind keyword -> Kind (the addressable instruction classes)
_KIND = {
    "mfma": Kind.MFMA, "ds_read": Kind.DS_READ, "ds_write": Kind.DS_WRITE,
    "vmem_load": Kind.VMEM_LOAD, "vmem_store": Kind.VMEM_STORE,
    "smem": Kind.SMEM, "valu": Kind.VALU, "salu": Kind.SALU,
}
_TOKEN_RE = re.compile(r"^([a-z_]+)\s*([#@])\s*(.+)$")


class ResolveError(KeyError):
    pass


@dataclass
class MoveResult:
    op: Dict
    ok: bool
    note: str = ""
    skipped: List[int] = field(default_factory=list)


def _of_kind(ed: RegionEditor, kind: Kind) -> List[int]:
    return [i for i in ed.order if ed.kind_of(i) is kind]


def resolve(ed: RegionEditor, handle: Handle) -> int:
    """Resolve a stable handle to an instruction id in ``ed``'s current order."""
    if isinstance(handle, int):
        if handle not in ed._line_of:
            raise ResolveError("unknown iid {}".format(handle))
        return handle
    tok = handle.strip()
    if tok.startswith("#"):
        return resolve(ed, int(tok[1:]))
    m = _TOKEN_RE.match(tok)
    if not m:
        raise ResolveError("unparseable handle {!r}".format(handle))
    kind_kw, sel, rest = m.group(1), m.group(2), m.group(3).strip()
    if kind_kw not in _KIND:
        raise ResolveError("unknown kind {!r} in handle {!r}".format(kind_kw, handle))
    members = _of_kind(ed, _KIND[kind_kw])
    if sel == "#":                       # nth of kind, 0-based
        n = int(rest)
        if not (0 <= n < len(members)):
            raise ResolveError("{}#{}: only {} present".format(kind_kw, n, len(members)))
        return members[n]
    # sel == "@": semantic anchor -- first of kind whose operands mention <reg>
    for i in members:
        ops = " ".join(ed._line_of[i].operands or [])
        if rest in ops:
            return i
    raise ResolveError("no {} mentions {!r}".format(kind_kw, rest))


def resolve_many(ed: RegionEditor, target: Union[Handle, Sequence[Handle]]) -> List[int]:
    if isinstance(target, (list, tuple)):
        return [resolve(ed, h) for h in target]
    return [resolve(ed, target)]


def apply_moves(ed: RegionEditor, moves: Sequence[Dict],
                strict: bool = False) -> List[MoveResult]:
    """Compile + apply a move-list onto ``ed`` (in place). Returns a per-op log.

    Illegal moves are skipped (recorded) unless ``strict`` (then raises via the
    editor). Caller materializes + runs the FixupPass pipeline afterwards."""
    log: List[MoveResult] = []
    for op in moves:
        kind = op.get("op")
        try:
            if kind == "keep":
                log.append(MoveResult(op, True, "keep (no-op)"))
                continue
            if kind in ("hoist", "move_after", "sink", "move_before"):
                after = kind in ("hoist", "move_after")
                anchor_key = "after" if after else "before"
                anchor = resolve(ed, op[anchor_key])
                targets = resolve_many(ed, op["target"])
                prev = anchor
                skipped: List[int] = []
                changed = False
                for t in targets:
                    d = (ed.move_after(t, prev, strict=strict) if after
                         else ed.move_before(t, prev, strict=strict))
                    if d.changed:
                        changed = True
                        prev = t            # chain: keep requested order in the gap
                    else:
                        skipped.extend(d.skipped)
                log.append(MoveResult(op, changed and not skipped,
                                      "moved {} skipped {}".format(
                                          len(targets) - len(skipped), len(skipped)),
                                      skipped))
            elif kind == "swap":
                a, b = resolve(ed, op["a"]), resolve(ed, op["b"])
                d = ed.swap(a, b, strict=strict)
                log.append(MoveResult(op, d.changed, d.note, d.skipped))
            elif kind == "layout":
                anchors = ed.anchors(_KIND.get(op.get("anchors", "mfma"), Kind.MFMA))
                slots = {int(g): resolve_many(ed, fillers)
                         for g, fillers in op["slots"].items()}
                d = ed.set_gap_layout(anchors, slots, strict=strict)
                log.append(MoveResult(op, d.changed and not d.skipped, d.note, d.skipped))
            else:
                raise ResolveError("unknown op {!r}".format(kind))
        except (KeyError, ResolveError) as exc:
            if strict:
                raise
            log.append(MoveResult(op, False, "resolve/apply error: {}".format(exc)))
    return log
