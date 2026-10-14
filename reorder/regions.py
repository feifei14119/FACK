"""CFG construction + region splitting (architecture-agnostic).

Pipeline:
  1. collect *code items* (INSTR / LABEL lines) inside the ``.text`` section
  2. build basic blocks (leaders = entry, branch targets, post-branch)
  3. add CFG edges (fallthrough + branch) using the Target for branch semantics
  4. find natural loops from back-edges (header dominates the latch; a
     non-dominating retreating branch is accepted only inside main code, which
     keeps rotated loops while rejecting cold-path / outlined-copy jumps back
     into a loop body)
  5. split the code into ordered regions: PROLOGUE / LOOP / INTER / EPILOGUE
     (or a single BODY region when there is no loop), then OUTLINED / LOOP for
     code placed after the last program end and reached only by jumps (cold
     tails, specialised copies, and sometimes the main loops themselves)

All branch detection / target resolution is delegated to ``Target`` so this
module contains no ISA knowledge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .model import Line, LineKind, Program

# section directives that switch out of executable code
_TEXT_DIRECTIVES = {".text"}
_NONTEXT_DIRECTIVES = {".rodata", ".data", ".bss", ".section"}


class RegionKind(Enum):
    PROLOGUE = "prologue"
    LOOP = "loop"
    INTER = "inter"
    EPILOGUE = "epilogue"
    BODY = "body"
    OUTLINED = "outlined"


@dataclass
class CodeItem:
    pos: int          # position within the code-item stream
    line_idx: int     # index into Program.lines
    line: Line


@dataclass
class BasicBlock:
    id: int
    start: int                       # first code-item pos (inclusive)
    end: int                         # last code-item pos (inclusive)
    label: Optional[str] = None      # entry label, if the block starts at one
    succ: List[int] = field(default_factory=list)   # successor block ids
    pred: List[int] = field(default_factory=list)

    @property
    def line_start(self) -> int:
        return self._line_start

    @property
    def line_end(self) -> int:
        return self._line_end

    _line_start: int = 0
    _line_end: int = 0


@dataclass
class Loop:
    header_label: str
    header_pos: int     # code-item pos of the header
    tail_pos: int       # code-item pos of the back-edge branch
    line_start: int
    line_end: int
    outlined: bool = False   # lives in the outlined code after the program end


@dataclass
class Region:
    kind: RegionKind
    line_start: int
    line_end: int
    header_label: Optional[str] = None
    outlined: bool = False


@dataclass
class RegionAnalysis:
    items: List[CodeItem]
    blocks: List[BasicBlock]
    loops: List[Loop]
    regions: List[Region]
    label_pos: Dict[str, int]
    outline_start: Optional[int] = None   # code-item pos where outlined code begins


def _collect_code_items(program: Program) -> List[CodeItem]:
    """Return INSTR/LABEL lines that live in the .text section, in order."""
    items: List[CodeItem] = []
    in_text = True  # default: before any section directive we assume .text
    seen_section = False
    for ln in program.lines:
        if ln.kind is LineKind.DIRECTIVE and ln.directive:
            d = ln.directive
            if d in _TEXT_DIRECTIVES:
                in_text = True
                seen_section = True
            elif d in _NONTEXT_DIRECTIVES:
                in_text = False
                seen_section = True
            continue
        if not in_text:
            continue
        if ln.kind in (LineKind.INSTR, LineKind.LABEL):
            items.append(CodeItem(pos=len(items), line_idx=ln.idx, line=ln))
    return items


def _build_blocks(items: List[CodeItem], target) -> (List[BasicBlock], Dict[str, int]):
    n = len(items)
    label_pos: Dict[str, int] = {}
    for it in items:
        if it.line.kind is LineKind.LABEL and it.line.label:
            label_pos[it.line.label] = it.pos

    # determine branch targets (so target labels become leaders)
    target_positions = set()
    for it in items:
        if it.line.kind is LineKind.INSTR and target.is_branch(it.line):
            tgt = target.branch_target(it.line)
            if tgt is not None and tgt in label_pos:
                target_positions.add(label_pos[tgt])

    # leaders
    leaders = set()
    if n:
        leaders.add(0)
    for it in items:
        if it.line.kind is LineKind.LABEL:
            leaders.add(it.pos)
        if it.line.kind is LineKind.INSTR and target.is_branch(it.line):
            if it.pos + 1 < n:
                leaders.add(it.pos + 1)
    leaders |= target_positions

    sorted_leaders = sorted(leaders)
    blocks: List[BasicBlock] = []
    pos_to_block: Dict[int, int] = {}
    for bi, ldr in enumerate(sorted_leaders):
        end = (sorted_leaders[bi + 1] - 1) if bi + 1 < len(sorted_leaders) else (n - 1)
        label = items[ldr].line.label if items[ldr].line.kind is LineKind.LABEL else None
        blk = BasicBlock(id=bi, start=ldr, end=end, label=label)
        blk._line_start = items[ldr].line_idx
        blk._line_end = items[end].line_idx
        blocks.append(blk)
        for p in range(ldr, end + 1):
            pos_to_block[p] = bi

    # edges
    for blk in blocks:
        last = items[blk.end].line
        is_branch = last.kind is LineKind.INSTR and target.is_branch(last)
        is_term = is_branch and target.is_terminator(last)
        is_cond = is_branch and target.is_conditional_branch(last)
        # fallthrough (unless unconditional terminator)
        if (not is_term) and blk.end + 1 < n:
            blk.succ.append(pos_to_block[blk.end + 1])
        # branch target
        if is_branch:
            tgt = target.branch_target(last)
            if tgt is not None and tgt in label_pos:
                blk.succ.append(pos_to_block[label_pos[tgt]])
        # de-dup while preserving order
        seen = set()
        blk.succ = [s for s in blk.succ if not (s in seen or seen.add(s))]

    for blk in blocks:
        for s in blk.succ:
            blocks[s].pred.append(blk.id)

    return blocks, label_pos


_PROGRAM_END = ("s_endpgm", "s_endpgm_saved")


def _is_program_end(line: Line, target) -> bool:
    fn = getattr(target, "is_program_end", None)
    if fn is not None:
        return bool(fn(line))
    return (line.opcode or "").lower() in _PROGRAM_END


def _outline_start(items: List[CodeItem], label_pos: Dict[str, int], target) -> Optional[int]:
    """First code-item pos of the outlined code after the LAST program end, or
    None. Only code that is a branch target counts (trailing ``s_code_end``
    padding stays in the epilogue); an early-exit ``s_endpgm`` in the middle of
    the kernel does not start outlined code because a later one exists."""
    last_end = None
    for it in items:
        if it.line.kind is LineKind.INSTR and _is_program_end(it.line, target):
            last_end = it.pos
    if last_end is None:
        return None
    targets = set()
    for it in items:
        if it.line.kind is LineKind.INSTR and target.is_branch(it.line):
            tgt = target.branch_target(it.line)
            if tgt in label_pos:
                targets.add(label_pos[tgt])
    if any(p > last_end for p in targets):
        return last_end + 1
    return None


def _block_index(items: List[CodeItem], blocks: List[BasicBlock]) -> List[int]:
    of = [0] * len(items)
    for b in blocks:
        for p in range(b.start, b.end + 1):
            of[p] = b.id
    return of


def _idoms(blocks: List[BasicBlock]) -> List[Optional[int]]:
    """Immediate dominators (Cooper-Harvey-Kennedy) rooted at block 0;
    unreachable blocks get None."""
    n = len(blocks)
    if not n:
        return []
    order: List[int] = []
    seen = [False] * n
    stack = [(0, 0)]
    seen[0] = True
    while stack:
        b, i = stack[-1]
        succ = blocks[b].succ
        if i < len(succ):
            stack[-1] = (b, i + 1)
            s = succ[i]
            if not seen[s]:
                seen[s] = True
                stack.append((s, 0))
        else:
            order.append(b)
            stack.pop()
    rpo = order[::-1]
    rank = {b: k for k, b in enumerate(rpo)}
    idom: List[Optional[int]] = [None] * n
    idom[0] = 0

    def meet(a: int, b: int) -> int:
        while a != b:
            while rank[a] > rank[b]:
                a = idom[a]
            while rank[b] > rank[a]:
                b = idom[b]
        return a

    changed = True
    while changed:
        changed = False
        for b in rpo[1:]:
            new = None
            for p in blocks[b].pred:
                if idom[p] is None or p not in rank:
                    continue
                new = p if new is None else meet(p, new)
            if new is not None and idom[b] != new:
                idom[b] = new
                changed = True
    return idom


def _dominates(idom: List[Optional[int]], a: int, b: int) -> Optional[bool]:
    """True/False if ``a`` dominates ``b``; None when ``b`` is unreachable."""
    if idom[b] is None:
        return None
    while True:
        if b == a:
            return True
        if b == 0:
            return False
        b = idom[b]


def _find_loops(items: List[CodeItem], blocks: List[BasicBlock],
                label_pos: Dict[str, int], target,
                outline_start: Optional[int] = None) -> List[Loop]:
    """Natural loops from back-edges.

    A retreating branch (target label earlier in program order) is a back-edge
    when its target block dominates the branch's block. A non-dominating one
    (rotated loops entered at the bottom) is accepted only when both ends are in
    main code -- a cold tail or an outlined copy jumping back into the middle of
    a loop body is control-flow re-entry, not a loop. When a header has a latch
    in main code, latches in the outlined code are dropped so the loop span
    stays the in-line body."""
    if outline_start is None:
        outline_start = len(items)
    blk_of = _block_index(items, blocks)
    idom = _idoms(blocks)
    loops: List[Loop] = []
    for it in items:
        if it.line.kind is not LineKind.INSTR or not target.is_branch(it.line):
            continue
        tgt = target.branch_target(it.line)
        if tgt is None or tgt not in label_pos:
            continue
        hpos = label_pos[tgt]
        if hpos > it.pos:
            continue
        dom = _dominates(idom, blk_of[hpos], blk_of[it.pos])
        in_main = it.pos < outline_start and hpos < outline_start
        if not dom and not in_main:
            continue
        loops.append(Loop(
            header_label=tgt,
            header_pos=hpos,
            tail_pos=it.pos,
            line_start=items[hpos].line_idx,
            line_end=items[it.pos].line_idx,
            outlined=hpos >= outline_start,
        ))
    main_headers = {lp.header_pos for lp in loops if lp.tail_pos < outline_start}
    loops = [lp for lp in loops
             if not (lp.tail_pos >= outline_start and lp.header_pos in main_headers)]
    # keep outermost, non-overlapping loops in program order
    loops.sort(key=lambda lp: (lp.header_pos, -lp.tail_pos))
    merged: List[Loop] = []
    for lp in loops:
        if merged and lp.header_pos <= merged[-1].tail_pos:
            # nested/overlapping -> extend the enclosing loop if needed
            if lp.tail_pos > merged[-1].tail_pos:
                merged[-1].tail_pos = lp.tail_pos
                merged[-1].line_end = lp.line_end
            continue
        merged.append(lp)
    return merged


def _split_regions(items: List[CodeItem], loops: List[Loop],
                   outline_start: Optional[int] = None) -> List[Region]:
    if not items:
        return []
    n = len(items)
    main_end = n if outline_start is None else outline_start
    main_loops = [lp for lp in loops if lp.header_pos < main_end]
    outlined_loops = [lp for lp in loops if lp.header_pos >= main_end]

    regions: List[Region] = []
    if main_end > 0:
        if not main_loops:
            kind = RegionKind.PROLOGUE if outlined_loops else RegionKind.BODY
            regions.append(Region(kind, items[0].line_idx, items[main_end - 1].line_idx))
        else:
            cursor_pos = 0  # code-item pos cursor
            for lp in main_loops:
                if lp.header_pos > cursor_pos:
                    kind = RegionKind.PROLOGUE if not regions else RegionKind.INTER
                    regions.append(Region(kind, items[cursor_pos].line_idx,
                                          items[lp.header_pos - 1].line_idx))
                regions.append(Region(RegionKind.LOOP, lp.line_start, lp.line_end,
                                      header_label=lp.header_label))
                cursor_pos = lp.tail_pos + 1
            if cursor_pos < main_end:
                regions.append(Region(RegionKind.EPILOGUE, items[cursor_pos].line_idx,
                                      items[main_end - 1].line_idx))

    def has_instr(lo: int, hi: int) -> bool:
        return any(items[p].line.kind is LineKind.INSTR for p in range(lo, hi + 1))

    cursor_pos = main_end
    for lp in outlined_loops:
        if lp.header_pos > cursor_pos and has_instr(cursor_pos, lp.header_pos - 1):
            regions.append(Region(RegionKind.OUTLINED, items[cursor_pos].line_idx,
                                  items[lp.header_pos - 1].line_idx, outlined=True))
        regions.append(Region(RegionKind.LOOP, lp.line_start, lp.line_end,
                              header_label=lp.header_label, outlined=True))
        cursor_pos = lp.tail_pos + 1
    if cursor_pos < n and has_instr(cursor_pos, n - 1):
        regions.append(Region(RegionKind.OUTLINED, items[cursor_pos].line_idx,
                              items[n - 1].line_idx, outlined=True))
    return regions


def region_instr_lines(program: Program, region: Region) -> List[Line]:
    """Instruction lines (in order) contained in a region's line span."""
    return [ln for ln in program.lines
            if region.line_start <= ln.idx <= region.line_end
            and ln.kind is LineKind.INSTR]


def _mfma_count(program: Program, target, region: Region) -> int:
    from .model import Kind
    return sum(1 for ln in region_instr_lines(program, region)
               if target.classify(ln.opcode or "", ln.operands) is Kind.MFMA)


def select_region(regions: List[Region], selector="loop",
                  program: Optional[Program] = None, target=None) -> Region:
    """Pick ONE region to tune from an analysis' region list.

    ``selector`` is either an int index into ``regions`` or a kind name with an
    optional 0-based occurrence suffix:
      "loop"             -> the hot loop: with ``program``/``target`` given, the
                            loop with the most MFMA/WMMA (ties and MFMA-free
                            kernels -> the first one); otherwise the first loop
      "loop#0"/"loop#1"  -> loops in program order (multi-loop kernels)
      "loop@<label>"     -> the loop whose header is ``<label>``
      "prologue"         -> pre-loop straight-line code
      "epilogue"         -> post-loop straight-line code
      "inter"            -> code between two loops
      "body"             -> the single region of a loop-less kernel
      "outlined"         -> non-loop code placed after the program end

    "loop" with no detected loop falls back to the first region (a loop-less
    kernel is one BODY/PROLOGUE region) so legacy callers keep working; any
    other missing kind raises ValueError so the caller gets clear feedback."""
    if not regions:
        raise ValueError("no regions to select from")
    if isinstance(selector, int):
        return regions[selector]
    sel = (selector or "loop").strip()
    if sel.lower().startswith("loop@"):
        label = sel[5:]
        for r in regions:
            if r.kind is RegionKind.LOOP and r.header_label == label:
                return r
        have = ", ".join(r.header_label for r in regions if r.kind is RegionKind.LOOP)
        raise ValueError("no loop with header %r (have: %s)" % (label, have))
    sel = sel.lower()
    if sel == "loop":
        loops = [r for r in regions if r.kind is RegionKind.LOOP]
        if loops:
            if program is not None and target is not None and len(loops) > 1:
                counts = [_mfma_count(program, target, r) for r in loops]
                return loops[counts.index(max(counts))]
            return loops[0]
    kind, _, occ = sel.partition("#")
    # Common misspelling in agent prompts / docs ("prolague" == prologue).
    if kind == "prolague":
        kind = "prologue"
    idx = int(occ) if occ else 0
    matches = [r for r in regions if r.kind.value == kind]
    if matches:
        return matches[min(idx, len(matches) - 1)]
    if kind in ("loop", "body"):
        return regions[0]
    have = ", ".join(sorted({r.kind.value for r in regions}))
    raise ValueError("no region of kind %r (have: %s)" % (kind, have))


def region_summaries(program: Program, regions: List[Region]) -> List[dict]:
    """JSON-able per-region metadata: index, kind, line span, header, instr count.
    The ``index`` is a stable selector accepted by ``select_region``."""
    out = []
    for i, r in enumerate(regions):
        out.append({"index": i, "kind": r.kind.value,
                    "line_start": r.line_start, "line_end": r.line_end,
                    "header_label": r.header_label, "outlined": r.outlined,
                    "instrs": len(region_instr_lines(program, r))})
    return out


def analyze(program: Program, target) -> RegionAnalysis:
    items = _collect_code_items(program)
    blocks, label_pos = _build_blocks(items, target)
    outl = _outline_start(items, label_pos, target)
    loops = _find_loops(items, blocks, label_pos, target, outl)
    regions = _split_regions(items, loops, outl)
    return RegionAnalysis(items=items, blocks=blocks, loops=loops,
                          regions=regions, label_pos=label_pos, outline_start=outl)
