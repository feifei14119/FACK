"""M6c: the search loop that ties direction (prior) + candidate generation +
real-HW GFLOPS (the verdict) together.

Design (per the M6b validation, proj/if/direction_signal_validation.md):
  * ``direction`` is a NOISY, COARSE prior -> used ONLY to pick which operator
    family to try first; it is voted over several captures, never trusted from a
    single one, and ignored when low-confidence.
  * the OBJECTIVE is measured GFLOPS, gated by correctness + the static Verifier;
    a candidate is accepted over the baseline only if it clears the baseline's
    own run-to-run noise floor.
  * candidate generation reuses the fixed-logic engine (optlevel ladder,
    compact_kind, the weighted list scheduler, and move-DSL) -- the search picks
    among legal-by-construction transforms; it never edits ASM text.

The evaluator is INJECTED (Protocol: ``evaluate(s_path, with_counters) ->
EvalResult``) so the loop is unit-testable without a GPU and runs on real HW via
``harness.evaluator.GpuTestcaseEvaluator`` (see tools/search_loop.py).
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from reorder import emitter, parser, regions, waitcnt
from reorder.editor import RegionEditor
from reorder.model import Kind
from reorder.verifier import Verifier
from isa.gfx942.target import Gfx942Target
from harness.measurement import measure_screen

from . import movedsl
from .list_scheduler import Weights, schedule, schedule_phase

_KIND_BY_NAME = {"vmem_load": Kind.VMEM_LOAD, "ds_read": Kind.DS_READ,
                 "valu": Kind.VALU, "salu": Kind.SALU}


def _default_target(prog):
    """Target for ``prog`` selected by its ``.amdgcn_target`` (default gfx942)."""
    from isa import registry
    return registry.target_for_program(prog)


def _post_passes(t) -> List:
    hook = getattr(t, "post_recompute_passes", None)
    if hook is not None:
        return hook()
    from isa.gfx942.passes import ForcedNopPass
    return [ForcedNopPass()]


_SEED_VIOLATIONS: Dict[tuple, frozenset] = {}


def _seed_violations(seed_src: str, make_target: Callable) -> frozenset:
    """Verifier findings of the unmodified seed (cached per seed/target)."""
    key = (hash(seed_src), make_target)
    if key not in _SEED_VIOLATIONS:
        prog = parser.parse(seed_src)
        t = make_target(prog)
        res = Verifier(t, reference=parser.parse(seed_src),
                       analysis=regions.analyze(prog, t)).verify(prog)
        _SEED_VIOLATIONS[key] = frozenset(res.violations)
    return _SEED_VIOLATIONS[key]


def _changed_span(before: List[int], after: List[int]) -> List[int]:
    """Line idxs of ``after`` between the common prefix and suffix with ``before``."""
    n = min(len(before), len(after))
    i = 0
    while i < n and before[i] == after[i]:
        i += 1
    if i == len(before) == len(after):
        return []
    j = 0
    while j < n - i and before[-1 - j] == after[-1 - j]:
        j += 1
    return after[i:len(after) - j]


def _is_hazard_line(ln) -> bool:
    op = (ln.opcode or "").lower()
    return op.startswith("s_wait") or op in ("s_set_vgpr_msb", "v_nop")


def _post_scope(prog, span: List[int]) -> set:
    """Lines the post passes may drop: the edited span, widened over the hazard
    lines right before it (they guarded whatever used to start the span)."""
    want = set(span)
    pos = [k for k, ln in enumerate(prog.lines) if ln.idx in want]
    if not pos:
        return set()
    lo, hi = pos[0], pos[-1]
    while lo > 0 and _is_hazard_line(prog.lines[lo - 1]):
        lo -= 1
    return {ln.idx for ln in prog.lines[lo:hi + 1]}


# --- candidate building (reuses the fixed-logic engine) --------------------
def build_candidate(seed_src: str, spec: Dict,
                    make_target: Callable = _default_target):
    """Apply one transform ``spec`` to the seed and return ``(text, verify_ok)``.

    spec kinds:
      {"kind": "ladder",    "level": N}                 recompute at OptLevel N
      {"kind": "compact",   "reorder_kind": "vmem_load", "earliest": True}
      {"kind": "listsched", "weights": Weights(...), "phase": k}   # phase optional:
                                                    # only phase k (reorder.phases) of the region
      {"kind": "movedsl",   "moves": [...]}
      {"kind": "layout",    "layout": {slot:int -> [filler_iid,...]},
                            "protect_prefetch": bool}     # AI per-slot layout (M7)
    Any spec may carry ``"region": <selector>`` (default "loop") to target the
    prologue / loop(s) / inter / epilogue independently (see
    regions.select_region). Loop edits use the loop-aware recompute; edits to a
    straight-line region use the whole-kernel CFG recompute so cross-region
    in-flight async ops stay correct. Every candidate ends with waitcnt
    recompute(opt_level) + ForcedNop, so it is legal-by-construction; the
    Verifier is the static backstop. Target post passes marked ``scoped`` only
    re-derive their lines inside the edited span and keep the seed's elsewhere
    (an unedited kernel stays byte-identical); ``"post_scope": "all"`` re-derives
    them kernel-wide.

    Verifier findings the unmodified seed already has (the seed is the
    known-correct reference; such findings are model gaps, e.g. opaque
    operands) do not fail the candidate -- the HW correctness test still
    gates it. ``"strict_verify": True`` fails on any finding."""
    prog = parser.parse(seed_src)
    t = make_target(prog)
    ref = parser.parse(seed_src)
    seed_idxs = [ln.idx for ln in prog.lines]
    _regs = regions.analyze(prog, t).regions
    region = regions.select_region(_regs, spec.get("region", "loop"), prog, t)
    opt_level = spec.get("opt_level", 1)
    kind = spec["kind"]

    if kind == "compact":
        ed = RegionEditor(prog, t, region, treat_waitcnt_as_fence=False)
        rk = _KIND_BY_NAME[spec["reorder_kind"]]
        ed.compact_kind(rk, earliest=spec.get("earliest", True))
        ed.materialize()
    elif kind == "listsched":
        ed = RegionEditor(prog, t, region, treat_waitcnt_as_fence=False)
        ed.order = schedule_phase(ed, spec.get("weights", Weights()), spec.get("phase"))
        if not ed.is_legal():
            return "", False
        ed.materialize()
    elif kind == "movedsl":
        ed = RegionEditor(prog, t, region, treat_waitcnt_as_fence=False)
        movedsl.apply_moves(ed, spec["moves"], strict=False)
        if not ed.is_legal():
            return "", False
        ed.materialize()
    elif kind == "layout":
        ed = RegionEditor(prog, t, region, treat_waitcnt_as_fence=False,
                          protect_prefetch=spec.get("protect_prefetch", False))
        anchors = ed.anchors(Kind.MFMA)
        layout = {int(k): list(v) for k, v in spec["layout"].items()}
        ed.set_gap_layout(anchors, layout, strict=False)
        if not ed.is_legal():
            return "", False
        ed.materialize()
    elif kind == "order":
        # anchor-less linear-order intent (M9 Phase 3): realise the requested
        # relative order greedily, each move legal-window gated.
        ed = RegionEditor(prog, t, region, treat_waitcnt_as_fence=False,
                          protect_prefetch=spec.get("protect_prefetch", False))
        prev = None
        for f in (int(x) for x in spec["order"]):
            if f not in ed._line_of:
                continue
            if prev is not None:
                ed.move_after(f, prev, strict=False)
            prev = f
        if not ed.is_legal():
            return "", False
        ed.materialize()
    elif kind != "ladder":
        raise ValueError("unknown spec kind {!r}".format(kind))
    span = _changed_span(seed_idxs, [ln.idx for ln in prog.lines])

    if region.kind is regions.RegionKind.LOOP:
        waitcnt.recompute(prog, t, region=region, opt_level=opt_level)
    else:
        # editing a straight-line region (prologue/inter/epilogue/body): thread
        # the scoreboard across ALL region boundaries so cross-region async ops
        # (e.g. loads issued in the loop, drained in the epilogue) stay correct.
        waitcnt.recompute_cfg(prog, t, opt_level=opt_level)
    scope = None if spec.get("post_scope") == "all" else _post_scope(prog, span)
    for p in _post_passes(t):
        if getattr(p, "scoped", False):
            p.run(prog, t, scope=scope)
        else:
            p.run(prog, t)
    a2 = regions.analyze(prog, t)
    res = Verifier(t, reference=ref, analysis=a2).verify(prog)
    ok = res.ok
    if not ok and not spec.get("strict_verify"):
        ok = set(res.violations) <= _seed_violations(seed_src, make_target)
    return emitter.emit(prog), ok


# --- direction: voted, low-confidence-aware --------------------------------
@dataclass
class DirectionVote:
    bottleneck: str
    confidence: float          # fraction of captures agreeing with the mode
    votes: Dict[str, int] = field(default_factory=dict)

    def trusted(self, min_conf: float = 0.6) -> bool:
        """A usable prior: a concrete hot dimension agreed on by enough captures
        (latency/none are non-actionable -> not trusted)."""
        return (self.bottleneck not in ("latency", "none")
                and self.confidence >= min_conf)


def vote_direction(evaluator, s_path: str, n: int = 5) -> DirectionVote:
    """Capture ``direction`` n times and vote (ATT sampling is noisy -- M6b)."""
    votes: Dict[str, int] = {}
    for _ in range(max(1, n)):
        res = evaluator.evaluate(s_path, with_counters=True)
        d = getattr(res, "direction", None)
        if d and d.get("bottleneck"):
            b = d["bottleneck"]
            votes[b] = votes.get(b, 0) + 1
    if not votes:
        return DirectionVote("none", 0.0, {})
    mode = max(votes, key=votes.get)
    return DirectionVote(mode, votes[mode] / sum(votes.values()), votes)


# --- operator prior + fixed fallback ---------------------------------------
def direction_to_specs(bottleneck: str) -> List[Dict]:
    """Operator families worth trying FIRST given a (trusted) bottleneck."""
    if bottleneck == "memory":
        return [
            {"kind": "compact", "reorder_kind": "vmem_load", "earliest": True},
            {"kind": "listsched", "weights": Weights(load_hoist=2.0, latency=0.5)},
        ]
    if bottleneck == "lds":
        return [
            {"kind": "compact", "reorder_kind": "ds_read", "earliest": True},
            {"kind": "compact", "reorder_kind": "ds_read", "earliest": False},
        ]
    if bottleneck in ("scalar", "scalar_mem"):
        return [{"kind": "compact", "reorder_kind": "salu", "earliest": True}]
    if bottleneck == "compute":
        # compute-bound: reorder gains are limited -> only gentle perturbations
        return [{"kind": "listsched", "weights": Weights(critical_path=1.5)}]
    return []


def fallback_specs() -> List[Dict]:
    """Fixed-logic ladder enumeration, used when direction is low-confidence."""
    return [
        {"kind": "compact", "reorder_kind": "vmem_load", "earliest": True},
        {"kind": "compact", "reorder_kind": "vmem_load", "earliest": False},
        {"kind": "listsched", "weights": Weights(load_hoist=1.0)},
        {"kind": "listsched", "weights": Weights(critical_path=1.5, latency=1.0)},
    ]


# --- the search loop -------------------------------------------------------
@dataclass
class Trial:
    name: str
    spec: Optional[Dict]
    correct: Optional[bool]
    tflops: Optional[float]
    accepted: bool = False
    note: str = ""


@dataclass
class SearchResult:
    best_name: str
    best_tflops: Optional[float]
    best_path: str
    baseline_tflops: Optional[float]
    direction: Optional[DirectionVote]
    trials: List[Trial] = field(default_factory=list)


def _median_tflops(evaluator, s_path: str, repeats: int):
    batch = measure_screen(evaluator, s_path, repeats)
    return batch.correct, batch.tflops


def search(seed_src: str, evaluator, *, make_target: Callable = _default_target,
           workdir: Optional[str] = None, perf_repeats: int = 3,
           direction_captures: int = 5, use_direction: bool = True,
           noise_margin: float = 0.0,
           extra_specs: Optional[List[Dict]] = None) -> SearchResult:
    """Coordinate-descent-style search: measure the baseline, vote direction to
    prioritise operators (with a fixed-ladder fallback), build + measure each
    candidate, and accept the fastest CORRECT one that clears ``noise_margin``.

    ``evaluator`` only needs ``evaluate(s_path, with_counters) -> EvalResult``
    (``.correct``, ``.tflops``, ``.direction``).

    ``extra_specs`` (M7 meta layer): a knowledge-seeded PRIOR list tried FIRST,
    before the direction-derived and fallback specs. It only re-orders what to
    try; every candidate is still correctness/Verifier/margin-gated, so a wrong
    prior can only waste budget, never produce a bad kernel."""
    workdir = workdir or tempfile.mkdtemp(prefix="testft_search_")
    os.makedirs(workdir, exist_ok=True)

    def write(name, text):
        p = os.path.join(workdir, "cand_%s.s" % name)
        with open(p, "w") as f:
            f.write(text)
        return p

    # baseline = L1 recompute (no reorder)
    base_text, base_ok = build_candidate(seed_src, {"kind": "ladder", "level": 1},
                                         make_target)
    base_path = write("baseline", base_text)
    base_correct, base_tflops = (_median_tflops(evaluator, base_path, perf_repeats)
                                 if base_ok else (None, None))
    trials = [Trial("baseline", {"kind": "ladder", "level": 1},
                    base_correct, base_tflops, accepted=bool(base_ok and base_correct),
                    note="seed L1")]
    if not base_ok or not base_correct or base_tflops is None:
        trials[0].note = "baseline failed static verification or screening"
        return SearchResult("baseline", None, base_path, None, None, trials)

    vote = None
    if use_direction:
        vote = vote_direction(evaluator, base_path, direction_captures)

    specs = list(extra_specs or [])    # M7 knowledge prior tried first
    if vote and vote.trusted():
        specs += direction_to_specs(vote.bottleneck) + fallback_specs()
    else:
        specs += fallback_specs()
    # de-dup while preserving order
    seen = set()
    uniq = []
    for s in specs:
        key = repr(sorted(s.items(), key=lambda kv: kv[0]))
        if key not in seen:
            seen.add(key)
            uniq.append(s)

    best_name, best_tflops, best_path = "baseline", base_tflops, base_path
    for i, spec in enumerate(uniq):
        name = "%s_%d" % (spec["kind"], i)
        text, ok = build_candidate(seed_src, spec, make_target)
        if not ok:
            trials.append(Trial(name, spec, None, None, note="verify failed"))
            continue
        p = write(name, text)
        correct, tflops = _median_tflops(evaluator, p, perf_repeats)
        better = (tflops is not None and best_tflops is not None
                  and tflops > best_tflops * (1.0 + noise_margin))
        accepted = bool(correct and better)
        trials.append(Trial(name, spec, correct, tflops, accepted=accepted))
        if accepted:
            best_name, best_tflops, best_path = name, tflops, p

    return SearchResult(best_name, best_tflops, best_path, base_tflops, vote, trials)
