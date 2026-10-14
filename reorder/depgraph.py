"""Architecture-agnostic dependency-graph framework + legal move windows.

The core holds the graph structure (nodes = instructions, typed edges = ordering
constraints) and computes, for any instruction, the ``legal_window`` it may be
moved into without violating a constraint. It contains **no ISA knowledge**:
all edges are added by ``Target.build_edges`` (see isa/gfx942/edges.py), and
which instructions are scheduling *fences* (barriers, exec writes, branches, and
-- conservatively, until M4 owns recompute -- existing waitcnt) is marked by the
Target as well.

A node's stable identity (``iid``) is its source line index, so moves and diffs
can refer to instructions independent of their current position.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .model import EdgeType, Line


@dataclass
class Node:
    iid: int                 # stable id == source line index
    pos: int                 # current order within the region (0-based)
    line: Line
    defs: Set = field(default_factory=set)   # register units written
    uses: Set = field(default_factory=set)   # register units read


class DepGraph:
    def __init__(self, nodes: List[Node]) -> None:
        self.nodes = nodes
        self.by_iid: Dict[int, Node] = {n.iid: n for n in nodes}
        self._out: Dict[int, Set[Tuple[int, EdgeType]]] = defaultdict(set)
        self._in: Dict[int, Set[Tuple[int, EdgeType]]] = defaultdict(set)
        self._fences: Set[int] = set()
        # per-pair minimum POSITION distance (>=1). A plain ordering edge needs
        # distance 1 (a strictly before b); a latency edge (e.g. MFMA write ->
        # non-MFMA read) needs ``dist`` issue slots between producer and consumer.
        self._dist: Dict[Tuple[int, int], int] = {}

    # --- construction ------------------------------------------------------
    def add_edge(self, a_iid: int, b_iid: int, etype: EdgeType, dist: int = 1) -> None:
        """Order constraint: ``a`` must precede ``b`` by at least ``dist`` slots
        (``dist == 1`` is a plain "a before b" ordering edge)."""
        if a_iid == b_iid or a_iid not in self.by_iid or b_iid not in self.by_iid:
            return
        self._out[a_iid].add((b_iid, etype))
        self._in[b_iid].add((a_iid, etype))
        key = (a_iid, b_iid)
        if dist > self._dist.get(key, 1):
            self._dist[key] = dist

    def dist(self, a_iid: int, b_iid: int) -> int:
        """Required minimum position distance ``pos[b] - pos[a]`` for the edge
        a->b (1 for a plain ordering edge)."""
        return self._dist.get((a_iid, b_iid), 1)

    def latency_edges(self) -> List[Tuple[int, int, int]]:
        """``(a, b, dist)`` for every edge whose required distance exceeds 1
        (e.g. MFMA-write -> non-MFMA-read). Plain ordering edges are already
        guaranteed by per-unit placement, so the distance-repair only needs
        these."""
        return [(a, b, d) for (a, b), d in self._dist.items() if d > 1]

    def mark_fence(self, iid: int) -> None:
        if iid in self.by_iid:
            self._fences.add(iid)

    # --- queries -----------------------------------------------------------
    def preds(self, iid: int) -> Set[int]:
        return {a for a, _ in self._in.get(iid, ())}

    def succs(self, iid: int) -> Set[int]:
        return {b for b, _ in self._out.get(iid, ())}

    def edges(self) -> List[Tuple[int, int, EdgeType]]:
        return [(a, b, t) for a, outs in self._out.items() for b, t in outs]

    def edges_of_type(self, etype: EdgeType) -> List[Tuple[int, int]]:
        return [(a, b) for a, outs in self._out.items() for b, t in outs if t is etype]

    def edge_types(self, a_iid: int, b_iid: int) -> Set[EdgeType]:
        """Edge types of every constraint a->b (empty if no edge)."""
        return {t for (b, t) in self._out.get(a_iid, ()) if b == b_iid}

    def is_fence(self, iid: int) -> bool:
        return iid in self._fences

    def fences(self) -> Set[int]:
        return set(self._fences)

    def add_fences(self, iids) -> None:
        """Pin extra instructions (e.g. control-flow join points the
        instruction-only graph cannot see)."""
        self._fences.update(i for i in iids if i in self.by_iid)

    @property
    def fence_positions(self) -> List[int]:
        return sorted(self.by_iid[i].pos for i in self._fences)

    def is_order_legal(self, order: List[int], fences: Optional[Set[int]] = None) -> bool:
        """True if ``order`` satisfies every dependency edge (a before b) and
        preserves each non-fence instruction's fence segment + the fence order.

        ``fences`` overrides which instructions act as fences (the editor may,
        for cold-start scheduling, choose to ignore existing waitcnt fences).
        """
        pos = {iid: i for i, iid in enumerate(order)}
        for a, b, _ in self.edges():
            if pos.get(b, -1) - pos.get(a, -1) < self.dist(a, b):
                return False
        build_order = [n.iid for n in self.nodes]
        if not self._fence_segments_preserved(build_order, order, fences):
            return False
        return True

    def _fence_segments_preserved(self, original: List[int], new: List[int],
                                  fences: Optional[Set[int]] = None) -> bool:
        fset = self._fences if fences is None else fences
        if not fset:
            return True

        def seg(order):
            out = {}
            s = 0
            for x in order:
                if x in fset:
                    s += 1
                else:
                    out[x] = s
            return out

        o, n = seg(original), seg(new)
        for x in new:
            if x in fset:
                continue
            if o.get(x) != n.get(x):
                return False
        of = [x for x in original if x in fset]
        nf = [x for x in new if x in fset]
        return of == nf

    # --- the core service for the editor (M3) ------------------------------
    def legal_window(self, iid: int) -> Tuple[int, int]:
        """Inclusive ``(lo, hi)`` position range this instruction may occupy.

        Clamped by (a) the surrounding fences and (b) the positions of its
        direct dependency predecessors/successors. A fence instruction is
        pinned to its own position.
        """
        n = self.by_iid[iid]
        if iid in self._fences:
            return (n.pos, n.pos)

        lo, hi = 0, len(self.nodes) - 1
        # clamp to enclosing fence interval
        for fp in self.fence_positions:
            if fp < n.pos:
                lo = max(lo, fp + 1)
            elif fp > n.pos:
                hi = min(hi, fp - 1)
                break
        # clamp to dependency neighbours (honouring per-edge latency distance)
        for a in self.preds(iid):
            lo = max(lo, self.by_iid[a].pos + self.dist(a, iid))
        for b in self.succs(iid):
            hi = min(hi, self.by_iid[b].pos - self.dist(iid, b))
        return (lo, hi)

    def is_movable(self, iid: int) -> bool:
        lo, hi = self.legal_window(iid)
        return hi > lo

    # --- factory -----------------------------------------------------------
    @classmethod
    def build(cls, instr_lines: List[Line], target) -> "DepGraph":
        """Build a graph over an ordered list of instruction Lines.

        Register def/use sets come from ``Target.parse_operands`` plus the
        Target's implicit operands; all ordering edges come from
        ``Target.build_edges``.
        """
        nodes: List[Node] = []
        for pos, ln in enumerate(instr_lines):
            defs, uses = target.def_use(ln.opcode or "", ln.operands)
            nodes.append(Node(iid=ln.idx, pos=pos, line=ln, defs=set(defs), uses=set(uses)))
        graph = cls(nodes)
        target.build_edges(nodes, graph)
        return graph
