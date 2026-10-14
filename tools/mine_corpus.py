"""Mode A static corpus miner: read GOLD (hand-optimized, roofline-grade) kernels
and mine region-scoped CANDIDATE skills WITHOUT running any hardware.

KERNEL-AGNOSTIC RED LINE: every feature comes from the semantic ``Kind`` mix
(reorder.model: mfma/vmem_load/ds_read/salu/valu/...), the CFG regions
(reorder.regions) and the dependency DAG (reorder.depgraph). NOTHING about GEMM
or any shape (m/n/k, qhead/ctx_len, ...) is assumed or emitted; a mined skill's
scope is keyed on structural features only, never a shape or a kernel name.

Pipeline (per kernel .s):
  parse -> regions.analyze (CFG) -> for EACH region build a RegionEditor +
  RegionCost -> extract a schedule SIGNATURE (Kind histogram, anchored?, vmem
  load hoist distance, MFMA gap-fill pattern, waitcnt clustering, prefetch) ->
  derive a GENERIC kernel_class from the primary region's op-mix (replacing the
  old hard-wired loop_kind="mfma_dense").

Across the corpus, signatures are grouped by (arch, kernel_class, region) and
turned into CANDIDATE skills (navigation-only). Mode A NEVER promotes to
"trusted" -- that needs measured corroboration (Mode B / online tuning). Outputs
land under study_case/study_out (skills/ + mine_report.md); a human promotes
reviewed skills into knowledge/engine/skills manually.

  python3.8 tools/mine_corpus.py [--corpus DIR] [--out DIR]
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn
from agent.knowledge import Skill
from agent.layout_planner import mfma_shape_class as mfma_class
from reorder import cost as cost_mod, parser, regions
from reorder.editor import RegionEditor
from reorder.model import Kind
from search import driver

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CORPUS = os.path.join(REPO, "study_case", "gold_corpus")
# Mining output is decoupled from the tuner's tune_out: mined CANDIDATE skills +
# report live under study_case/study_out; promote reviewed ones into knowledge/engine/skills.
DEFAULT_OUT = os.path.join(REPO, "study_case", "study_out")

# Memory-ish / compute-ish kind groups used by the generic classifier + mapping.
_VMEM = (Kind.VMEM_LOAD, Kind.VMEM_STORE)
_DS = (Kind.DS_READ, Kind.DS_WRITE)


# ---------------------------------------------------------------------------
# Per-region schedule signature (kernel-agnostic)
# ---------------------------------------------------------------------------
def _frac(counter: Counter, kinds, total: int) -> float:
    if not total:
        return 0.0
    return round(sum(counter.get(k.value, 0) for k in kinds) / total, 3)


def _stats(values: List[float]) -> Optional[Dict]:
    """Compact distribution summary of a measured sample. Returns None for an
    empty sample so downstream code can tell "not observed" from "observed 0"."""
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n == 0:
        return None
    if n == 1:
        q1 = med = q3 = vals[0]
    else:
        # statistics.quantiles needs n>=2; fall back to median for tiny samples.
        med = statistics.median(vals)
        try:
            q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
        except statistics.StatisticsError:
            q1 = q3 = med
    return {
        "n": n,
        "min": round(vals[0], 2),
        "p25": round(q1, 2),
        "median": round(med, 2),
        "p75": round(q3, 2),
        "max": round(vals[-1], 2),
        "mean": round(statistics.fmean(vals), 2),
    }


# Kinds whose fine-grained placement the agent actually steers (loads/lds/vector
# work the schedule interleaves into MFMA gaps). MFMA/waitcnt/branch are anchors
# or fences, not free fillers, so they are excluded from the quant profile.
_QUANT_KINDS = (Kind.VMEM_LOAD, Kind.VMEM_STORE, Kind.DS_READ, Kind.DS_WRITE,
                Kind.VALU, Kind.SALU, Kind.SMEM)
_QUANT_KIND_VALUES = frozenset(k.value for k in _QUANT_KINDS)


# ---------------------------------------------------------------------------
# Instruction SUB-TYPING (within a coarse Kind)
# ---------------------------------------------------------------------------
# A single coarse Kind (mfma / ds_read / vmem_load ...) hides hardware-relevant
# variants: MFMA shapes (16x16x16 vs 32x32x8) have DIFFERENT result latency, so
# the gap they open -- and how many/which instructions fit it -- differs; LDS /
# VMEM ops have DIFFERENT transfer widths (b32/b64/b128, dword/dwordx2/x4). The
# miner must therefore key gap metrics on the MFMA shape and break capacity down
# by access width, instead of pooling everything into one "mfma"/"ds_read" bucket.
# ``mfma_class`` (shape token) is imported from agent.layout_planner so the miner
# (which keys measured stats) and the planner (which sizes placement) agree.
_WIDTH_B_RE = re.compile(r"_b(\d+)\b")
_WIDTH_DWORDX_RE = re.compile(r"dwordx(\d+)")


def access_width_bits(opcode: Optional[str]) -> Optional[int]:
    """Best-effort transfer width (bits) of a memory / LDS op, so b128 and
    dwordx4 (both 128-bit) compare on one axis. Returns None when not width-typed
    (the op is then pooled under the bare Kind, never mis-bucketed)."""
    if not opcode:
        return None
    m = _WIDTH_B_RE.search(opcode)
    if m:
        return int(m.group(1))
    m = _WIDTH_DWORDX_RE.search(opcode)
    if m:
        return 32 * int(m.group(1))
    if "dword" in opcode:        # plain ...dword (no xN) == 32-bit
        return 32
    for tok, bits in (("short", 16), ("ubyte", 8), ("sbyte", 8), ("byte", 8)):
        if tok in opcode:
            return bits
    return None


def filler_subkind(opcode: Optional[str]) -> Optional[str]:
    """Width label (e.g. ``"128b"``) used to sub-divide a filler Kind's capacity;
    None when the op carries no decodable width (handled at coarse-Kind level)."""
    bits = access_width_bits(opcode)
    return ("%db" % bits) if bits else None


def _gap_block_metrics(gaps_inner: List[List[int]],
                       kinds_of: Dict[int, str],
                       subkind_of: Dict[int, Optional[str]]) -> Dict:
    """Gap-fill metrics over ONE homogeneous block of gaps (either every gap in a
    region, or just the gaps that follow a single MFMA shape). Computes:
      * mfma_gap_size     -- gap length distribution
      * per_slot_capacity -- per Kind count/gap, each with a ``by_width`` breakdown
                             (b32/b64/b128 ...) so a wide ds_read is not pooled
                             with a narrow one
      * intra_gap_order   -- P(a before b | both in gap), schedulable fillers only
      * adjacent_cooccur  -- per Kind, fraction of adjacent gap-pairs filling BOTH
    Raw lists are kept so the corpus aggregator can pool across kernels."""
    gap_sizes = [len(g) for g in gaps_inner]
    gap_kind_seqs: List[List[str]] = []
    gap_has_kind: List[set] = []

    # widths actually present per Kind, so per-gap raw lists stay aligned (incl. 0).
    widths_per_kind: Dict[str, set] = defaultdict(set)
    for inner in gaps_inner:
        for i in inner:
            k, w = kinds_of[i], subkind_of.get(i)
            if k in _QUANT_KIND_VALUES and w:
                widths_per_kind[k].add(w)

    per_kind_counts: Dict[str, List[int]] = {k.value: [] for k in _QUANT_KINDS}
    per_width_counts: Dict[str, Dict[str, List[int]]] = {
        k: {w: [] for w in ws} for k, ws in widths_per_kind.items()}
    for inner in gaps_inner:
        seq = [kinds_of[i] for i in inner]
        gap_kind_seqs.append(seq)
        gap_has_kind.append(set(seq))
        cnt = Counter(seq)
        for k in per_kind_counts:
            per_kind_counts[k].append(cnt.get(k, 0))
        wcnt: Dict[str, Counter] = defaultdict(Counter)
        for i in inner:
            w = subkind_of.get(i)
            if w:
                wcnt[kinds_of[i]][w] += 1
        for k, ws in per_width_counts.items():
            for w in ws:
                ws[w].append(wcnt.get(k, {}).get(w, 0))

    per_slot_capacity: Dict[str, Dict] = {}
    for k, counts in per_kind_counts.items():
        if not any(counts):
            continue
        entry: Dict = {"stats": _stats(counts), "raw": counts}
        by_width = {w: {"stats": _stats(wc), "raw": wc}
                    for w, wc in per_width_counts.get(k, {}).items() if any(wc)}
        if by_width:
            entry["by_width"] = by_width
        per_slot_capacity[k] = entry

    # intra-gap type order: for each unordered pair present together in a gap,
    # how often does a precede b (by first occurrence)? Only over SCHEDULABLE
    # fillers (_QUANT_KINDS) -- fences/anchors (branch/barrier/waitcnt/set_m0)
    # are pinned region structure, not free fillers, so they would only add
    # tautological "X before branch" noise the agent can never act on.
    pair_before: Counter = Counter()
    pair_both: Counter = Counter()
    for seq in gap_kind_seqs:
        first = {}
        for idx, k in enumerate(seq):
            if k not in _QUANT_KIND_VALUES:
                continue
            first.setdefault(k, idx)
        present = sorted(first)
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                pair_both[(a, b)] += 1
                if first[a] < first[b]:
                    pair_before[(a, b)] += 1
    intra_gap_order = []
    for (a, b), both in pair_both.items():
        if both < 2:
            continue
        freq = pair_before[(a, b)] / both
        if freq >= 0.7:
            intra_gap_order.append({"before": a, "after": b,
                                    "freq": round(freq, 2), "n": both})
        elif freq <= 0.3:
            intra_gap_order.append({"before": b, "after": a,
                                    "freq": round(1 - freq, 2), "n": both})

    # adjacent-slot co-occurrence: of adjacent gap pairs, how many have the kind
    # in BOTH gaps (high => "ok to fill neighbours", low => "spread them out").
    adjacent_cooccur = {}
    n_pairs = len(gap_has_kind) - 1
    if n_pairs >= 1:
        for k in (kk.value for kk in _QUANT_KINDS):
            both = sum(1 for s in range(n_pairs)
                       if k in gap_has_kind[s] and k in gap_has_kind[s + 1])
            either = sum(1 for s in range(n_pairs)
                         if k in gap_has_kind[s] or k in gap_has_kind[s + 1])
            if either:
                adjacent_cooccur[k] = {"rate": round(both / either, 2),
                                       "both": both, "either": either,
                                       "n_pairs": n_pairs}

    return {
        "n_slots": len(gap_sizes),
        "mfma_gap_size": {"stats": _stats(gap_sizes), "raw": gap_sizes},
        "per_slot_capacity": per_slot_capacity,
        "intra_gap_order": intra_gap_order,
        "adjacent_cooccur": adjacent_cooccur,
    }


def quant_profile(ed, order, pos, anchors) -> Optional[Dict]:
    """MEASURED, fine-grained MFMA-gap layout of ONE anchored region (gold order).

    Every number is read straight off the gold schedule -- the miner never invents
    a value. The top-level fields pool over ALL gaps (back-compatible), but the
    KEY refinement is ``by_mfma_class``: gaps are bucketed by the SHAPE of the MFMA
    that opens them (16x16x16 vs 32x32x8 ...), because each shape has a different
    result latency and therefore a different gap size / filler capacity. Pooling
    them blindly (the old behaviour) blends a 3-cycle gap with a 6-cycle one. LDS /
    VMEM capacity is further split ``by_width`` (b32/b64/b128) within each Kind."""
    if len(anchors) < 2:
        return None

    kinds_of = {iid: ed.kind_of(iid).value for iid in order}
    subkind_of = {iid: filler_subkind(ed.opcode_of(iid)) for iid in order}

    gaps_inner: List[List[int]] = []
    gap_class: List[str] = []               # MFMA shape opening each gap
    for s in range(len(anchors) - 1):
        lo, hi = pos[anchors[s]], pos[anchors[s + 1]]
        gaps_inner.append([order[p] for p in range(lo + 1, hi)])
        gap_class.append(mfma_class(ed.opcode_of(anchors[s])))

    profile = _gap_block_metrics(gaps_inner, kinds_of, subkind_of)

    # burst run-length: longest consecutive same-kind run anywhere in the order
    # (region-global, not gap-scoped) -- kept at coarse-Kind granularity.
    runlens: Dict[str, List[int]] = {k.value: [] for k in _QUANT_KINDS}
    run_kind, run_len = None, 0
    for iid in order:
        k = kinds_of[iid]
        if k == run_kind:
            run_len += 1
        else:
            if run_kind in runlens and run_len:
                runlens[run_kind].append(run_len)
            run_kind, run_len = k, 1
    if run_kind in runlens and run_len:
        runlens[run_kind].append(run_len)
    profile["burst_runlen"] = {
        k: {"stats": _stats(rl), "raw": rl} for k, rl in runlens.items() if rl}

    # per-MFMA-shape breakdown: the same gap metrics, but only over the gaps a
    # given MFMA shape opens. This is the fix for "one mfma kind" -- a 32x32x8
    # gap genuinely holds more than a 16x16x16 gap, and the agent needs both.
    by_mfma_class: Dict[str, Dict] = {}
    for cls in sorted(set(gap_class)):
        sub = [gaps_inner[i] for i in range(len(gaps_inner)) if gap_class[i] == cls]
        by_mfma_class[cls] = _gap_block_metrics(sub, kinds_of, subkind_of)
    profile["by_mfma_class"] = by_mfma_class
    profile["mfma_class_hist"] = dict(Counter(gap_class))
    return profile


def region_signature(program, target, region) -> Dict:
    """Structural signature of ONE region in its (gold) current order. Reuses the
    same primitives observe() exposes: kind_of / legal windows via the DepGraph,
    MFMA anchors, RegionCost, and cross-iteration prefetch recognition."""
    ed = RegionEditor(program, target, region,
                      treat_waitcnt_as_fence=False, protect_prefetch=False)
    order = ed.order
    pos = {iid: i for i, iid in enumerate(order)}
    n = len(order)

    hist = Counter(ed.kind_of(i).value for i in order)
    anchors = ed.anchors(Kind.MFMA)
    anchored = bool(anchors)

    # vmem-load hoist distance: slots between a load and its first in-region
    # consumer (larger => issued earlier, more latency hidden).
    hoist_gaps: List[int] = []
    for iid in order:
        if ed.kind_of(iid) is not Kind.VMEM_LOAD:
            continue
        succ_pos = [pos[s] for s in ed.graph.succs(iid) if s in pos]
        if succ_pos:
            hoist_gaps.append(min(succ_pos) - pos[iid])

    # MFMA gap-fill pattern (anchored only): fillers per gap + their kinds.
    fills_per_gap: List[int] = []
    gap_kind_hist: Counter = Counter()
    for s in range(len(anchors) - 1):
        lo, hi = pos[anchors[s]], pos[anchors[s + 1]]
        inner = [order[p] for p in range(lo + 1, hi)]
        fills_per_gap.append(len(inner))
        for i in inner:
            gap_kind_hist[ed.kind_of(i).value] += 1

    rc = cost_mod.estimate(program, target, region)
    # avg async ops drained per wait: higher => "one wait covers many" clustering.
    cluster = round(rc.wait_stalls / rc.n_waits, 2) if rc.n_waits else 0.0

    try:
        prefetch_n = len(ed.prefetch_info().producers)
    except Exception:
        prefetch_n = 0

    quant = quant_profile(ed, order, pos, anchors) if anchored else None

    return {
        "n_instr": n,
        "kind_hist": dict(hist),
        "anchored": anchored,
        "frac": {
            "mfma": _frac(hist, (Kind.MFMA,), n),
            "vmem": _frac(hist, _VMEM, n),
            "ds": _frac(hist, _DS, n),
            "valu": _frac(hist, (Kind.VALU,), n),
            "salu": _frac(hist, (Kind.SALU,), n),
            "smem": _frac(hist, (Kind.SMEM,), n),
        },
        "vmem_load_hoist_median": (round(statistics.median(hoist_gaps), 1)
                                   if hoist_gaps else None),
        "gap_fill_avg": (round(statistics.fmean(fills_per_gap), 2)
                         if fills_per_gap else None),
        "gap_fill_nonuniform": (round(statistics.pstdev(fills_per_gap), 2)
                                if len(fills_per_gap) > 1 else 0.0),
        "gap_fill_kinds": dict(gap_kind_hist),
        "waitcnt_cluster": cluster,
        "n_waits": rc.n_waits,
        "est_cycles": rc.est_cycles,
        "prefetch_loads": prefetch_n,
        "quant": quant,
    }


# ---------------------------------------------------------------------------
# Generic structural classifier (replaces hard-wired loop_kind="mfma_dense")
# ---------------------------------------------------------------------------
def classify_kernel(region_records: List[Dict], meta: Optional[Dict] = None) -> str:
    """Derive a generic ``kernel_class`` from the PRIMARY region's op-mix. A
    sidecar meta.json may override via "kernel_class" or "family"."""
    meta = meta or {}
    if meta.get("kernel_class"):
        return str(meta["kernel_class"])
    if meta.get("family"):
        return str(meta["family"])

    prim = _primary_region(region_records)
    if prim is None:
        return "unknown"
    f = prim["signature"]["frac"]
    if prim["signature"]["anchored"]:
        return "mfma_dense" if f["mfma"] >= 0.15 else "mfma_sparse"
    if f["ds"] >= 0.25:
        return "lds_bound"
    if f["vmem"] >= 0.30 and f["valu"] < 0.15:
        return "memory_streaming"
    if f["valu"] >= 0.30:
        return "vector_only"
    return "mixed"


def _primary_region(region_records: List[Dict]) -> Optional[Dict]:
    """The region a kernel's class is judged on: the LARGEST loop (by instruction
    count), else the largest body, else the largest region overall.

    Picking the largest loop -- not the first -- matters for real kernels: split-k
    / pipelined GEMMs often contain several tiny control loops (loop(4)/loop(5)
    spin/accumulate blocks) alongside the real MFMA loop(s); judging the class on
    a tiny first loop would misclassify an mfma-dense kernel as 'mixed'."""
    if not region_records:
        return None
    for kind in ("loop", "body"):
        of_kind = [r for r in region_records if r["kind"] == kind]
        if of_kind:
            return max(of_kind, key=lambda r: r["signature"]["n_instr"])
    return max(region_records, key=lambda r: r["signature"]["n_instr"])


# ---------------------------------------------------------------------------
# Region-aware "signature -> candidate spec" mapping (three regions, three
# strategies). Specs use the build_candidate vocabulary the search already
# understands (search.driver.build_candidate). Evidence-driven: a spec is only
# suggested when the gold region actually exhibits the pattern.
# ---------------------------------------------------------------------------
def region_specs(region_kind: str, sig: Dict) -> Tuple[List[Dict], str]:
    specs: List[Dict] = []
    notes: List[str] = []
    f = sig["frac"]
    has_load = sig["kind_hist"].get("vmem_load", 0) > 0
    has_ds = sig["kind_hist"].get("ds_read", 0) > 0

    if region_kind in ("loop", "inter", "body") and sig["anchored"]:
        # core compute region (a loop, or a loop-less kernel's single anchored
        # body): keep MFMA fed by interleaving memory into its gaps.
        gk = sig.get("gap_fill_kinds", {})
        if has_load and gk.get("vmem_load", 0) > 0:
            specs.append({"kind": "distribute_evenly", "kinds": ["vmem_load"]})
            specs.append({"kind": "compact", "reorder_kind": "vmem_load", "earliest": True})
        if has_ds and gk.get("ds_read", 0) > 0:
            specs.append({"kind": "distribute_evenly", "kinds": ["ds_read"]})
        if sig.get("gap_fill_nonuniform", 0.0) >= 1.0:
            notes.append("gold uses a NON-UNIFORM MFMA gap layout (fillers/gap vary)")
        specs.append({"kind": "listsched", "weights": {"critical_path": 1.5}})
        notes.append("overlap memory with MFMA; fill gaps to keep the matrix engine busy")

    elif region_kind == "prologue":
        # pre-loop setup: front-load the first global/scalar loads before the
        # loop starts so their latency is hidden by setup work.
        if has_load and (sig.get("vmem_load_hoist_median") or 0) >= 2:
            specs.append({"kind": "compact", "reorder_kind": "vmem_load", "earliest": True})
            notes.append("gold issues the first vmem loads early (hoisted before use)")
        if f["smem"] > 0:
            specs.append({"kind": "compact", "reorder_kind": "smem", "earliest": True})
            notes.append("hoist scalar loads early in the prologue")
        specs.append({"kind": "listsched", "weights": {"critical_path": 1.5, "latency": 1.0}})

    elif region_kind == "epilogue":
        # post-loop drain / write-back: no prefetch; schedule the reorder by
        # dependency to drain efficiently (order/listsched, not gap-fill).
        notes.append("drain/write-back region: schedule by dependency; do NOT prefetch")
        specs.append({"kind": "listsched", "weights": {"critical_path": 1.5, "latency": 1.0}})

    else:  # body or anchor-less loop: dependency reorder
        specs.append({"kind": "listsched", "weights": {"critical_path": 1.5, "latency": 1.0}})
        notes.append("anchor-less region: reorder by dependency to lower est_cycles")

    # de-dup specs by their stable transform id, preserving first-seen order.
    seen, uniq = set(), []
    for sp in specs:
        key = kn._transform_id(sp)
        if key not in seen:
            seen.add(key)
            uniq.append(sp)
    return uniq, "; ".join(notes)


# ---------------------------------------------------------------------------
# Mine one kernel (the testable unit) and the whole corpus
# ---------------------------------------------------------------------------
def mine_kernel(name: str, src: str, meta: Optional[Dict] = None) -> Dict:
    """Analyse one gold kernel's source into a record:
    {name, arch, kernel_class, regions:[{kind, signature, specs, note}]}."""
    meta = meta or {}
    prog = parser.parse(src)
    target = driver._default_target(prog)
    regs = regions.analyze(prog, target).regions

    region_records: List[Dict] = []
    for r in regs:
        sig = region_signature(prog, target, r)
        region_records.append({"kind": r.kind.value, "signature": sig})

    kernel_class = classify_kernel(region_records, meta)
    arch = str(meta.get("arch", "gfx942"))
    for rec in region_records:
        specs, note = region_specs(rec["kind"], rec["signature"])
        rec["specs"] = specs
        rec["note"] = note
    return {"name": name, "arch": arch, "kernel_class": kernel_class,
            "regions": region_records}


def _iter_corpus(corpus_dir: str):
    """Yield (name, src_text, meta) for every kernel under ``corpus_dir``.

    A kernel is either (a) a subdirectory containing one or more ``.s`` files
    (``kernel.s`` preferred) with an optional ``meta.json`` sidecar, or (b) a
    bare ``*.s`` file directly under ``corpus_dir``."""
    if not os.path.isdir(corpus_dir):
        return
    for entry in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, entry)
        if os.path.isdir(path):
            s_files = sorted(f for f in os.listdir(path) if f.endswith(".s"))
            if not s_files:
                continue
            s_name = "kernel.s" if "kernel.s" in s_files else s_files[0]
            meta = {}
            meta_path = os.path.join(path, "meta.json")
            if os.path.isfile(meta_path):
                with open(meta_path) as fh:
                    meta = json.load(fh)
            with open(os.path.join(path, s_name)) as fh:
                yield entry, fh.read(), meta
        elif entry.endswith(".s"):
            with open(path) as fh:
                yield entry[:-2], fh.read(), {}


def mine_corpus(corpus_dir: str) -> List[Dict]:
    records = []
    for name, src, meta in _iter_corpus(corpus_dir):
        try:
            records.append(mine_kernel(name, src, meta))
        except Exception as e:  # one bad kernel must not abort the whole corpus
            sys.stderr.write("[mine] skip %s: %s\n" % (name, e))
    return records


# ---------------------------------------------------------------------------
# Aggregate corpus records into CANDIDATE skills (status never auto-trusted)
# ---------------------------------------------------------------------------
def build_skills(records: List[Dict]) -> List[Skill]:
    # group region observations by (arch, kernel_class, region_kind)
    groups: Dict[Tuple[str, str, str], List[Tuple[str, Dict]]] = defaultdict(list)
    for rec in records:
        for rr in rec["regions"]:
            key = (rec["arch"], rec["kernel_class"], rr["kind"])
            groups[key].append((rec["name"], rr))

    skills: List[Skill] = []
    for (arch, kernel_class, region_kind), items in sorted(groups.items()):
        # union of suggested specs, ranked by how many kernels suggested each.
        spec_support: Counter = Counter()
        spec_by_id: Dict[str, Dict] = {}
        notes: Counter = Counter()
        kernels = sorted({name for name, _ in items})
        for name, rr in items:
            seen_ids = set()
            for sp in rr["specs"]:
                tid = kn._transform_id(sp)
                spec_by_id.setdefault(tid, sp)
                if tid not in seen_ids:        # count each kernel once per spec
                    seen_ids.add(tid)
                    spec_support[tid] += 1
            if rr["note"]:
                notes[rr["note"]] += 1

        if not spec_by_id:
            continue
        ranked = [spec_by_id[tid] for tid, _ in spec_support.most_common()]
        n_k = len(kernels)
        top_support = spec_support.most_common(1)[0][1] if spec_support else 0
        agreement = top_support / n_k if n_k else 0.0
        confidence = round(min(0.9, agreement * (1 - 1.0 / (n_k + 1))), 3)
        note_txt = "; ".join(n for n, _ in notes.most_common(3))

        action: Dict = {"specs": ranked}
        if note_txt:
            action["note"] = note_txt
        # scope: structural features ONLY -- no shape, no kernel name.
        when = {"arch": arch, "loop_kind": kernel_class, "region": region_kind}
        skills.append(Skill(
            id="gold-%s-%s" % (kernel_class, region_kind),
            statement="[gold-mined, static] %s/%s: prefer %s"
                      % (kernel_class, region_kind,
                         ", ".join(kn._transform_id(s) for s in ranked[:3])),
            when=when,
            action=action,
            evidence={"kernels": kernels, "n_samples": n_k, "source": "gold_corpus(modeA)"},
            effect={"note": "static-mined; unmeasured (Mode A) -- needs HW corroboration"},
            confidence=confidence,
            status="candidate",   # Mode A never auto-promotes to trusted
        ))
    return skills


# ---------------------------------------------------------------------------
# Aggregate the fine-grained QUANT profiles into measured CONSTRAINT skills.
# These carry numeric ranges (gap size, per-slot capacity, burst, ordering,
# adjacency) + a per-constraint weight + conflict_groups, exactly the prior the
# (external) tuning agent reads to lay out a fresh, un-scheduled kernel. Every
# number is POOLED from the gold corpus -- never invented (Mode A red line).
# ---------------------------------------------------------------------------
def _support_weight(n_kernels: int, agreement: float = 1.0) -> float:
    """Weight in (0, 0.9]: rises with #independent kernels and with agreement."""
    return round(min(0.9, max(0.0, agreement) * (1 - 1.0 / (n_kernels + 1))), 3)


def _pool_quant(quants: List[Dict]) -> Dict:
    """Pool a list of per-region quant profiles (same arch/class/region)."""
    gap_raw: List[int] = []
    cap_raw: Dict[str, List[int]] = defaultdict(list)
    cap_support: Counter = Counter()      # #kernels where this kind appears
    burst_raw: Dict[str, List[int]] = defaultdict(list)
    order_both: Counter = Counter()
    order_before: Counter = Counter()
    coc_both: Counter = Counter()
    coc_either: Counter = Counter()
    coc_pairs: Counter = Counter()
    for q in quants:
        gap_raw.extend(q["mfma_gap_size"]["raw"])
        for k, v in q.get("per_slot_capacity", {}).items():
            cap_raw[k].extend(v["raw"])
            cap_support[k] += 1
        for k, v in q.get("burst_runlen", {}).items():
            burst_raw[k].extend(v["raw"])
        for o in q.get("intra_gap_order", []):
            a, b = o["before"], o["after"]
            order_both[(a, b)] += o["n"]
            order_before[(a, b)] += int(round(o["freq"] * o["n"]))
        for k, c in q.get("adjacent_cooccur", {}).items():
            coc_both[k] += c["both"]
            coc_either[k] += c["either"]
            coc_pairs[k] += c["n_pairs"]
    return {
        "gap_raw": gap_raw, "cap_raw": cap_raw, "cap_support": cap_support,
        "burst_raw": burst_raw, "order_both": order_both,
        "order_before": order_before, "coc_both": coc_both,
        "coc_either": coc_either, "coc_pairs": coc_pairs,
    }


def _pool_quant_by_class(quants: List[Dict]) -> Dict[str, Dict]:
    """Pool the ``by_mfma_class`` breakdowns across regions, keyed by MFMA shape.
    Returns per-shape gap / capacity(+width) / adjacency / ordering aggregates."""
    def _mk():
        return {"gap": [], "cap": defaultdict(list), "cap_w": defaultdict(list),
                "support": Counter(), "w_support": Counter(),
                "coc_both": Counter(), "coc_either": Counter(), "coc_pairs": Counter(),
                "order_both": Counter(), "order_before": Counter()}
    out: Dict[str, Dict] = defaultdict(_mk)
    for q in quants:
        for cls, m in q.get("by_mfma_class", {}).items():
            o = out[cls]
            o["gap"].extend(m["mfma_gap_size"]["raw"])
            for k, cap in m.get("per_slot_capacity", {}).items():
                o["cap"][k].extend(cap["raw"])
                o["support"][k] += 1
                for w, wc in cap.get("by_width", {}).items():
                    o["cap_w"][(k, w)].extend(wc["raw"])
                    o["w_support"][(k, w)] += 1
            for k, c in m.get("adjacent_cooccur", {}).items():
                o["coc_both"][k] += c["both"]
                o["coc_either"][k] += c["either"]
                o["coc_pairs"][k] += c["n_pairs"]
            for ordr in m.get("intra_gap_order", []):
                a, b = ordr["before"], ordr["after"]
                o["order_both"][(a, b)] += ordr["n"]
                o["order_before"][(a, b)] += int(round(ordr["freq"] * ordr["n"]))
    return out


def _class_constraints(quants: List[Dict], n_k: int
                       ) -> Tuple[List[Dict], List[List[str]]]:
    """Per-MFMA-shape refinements layered ON TOP of the pooled constraints, plus
    per-shape conflict groups. Returns ``(constraints, conflict_groups)``.

    When >1 MFMA shape exists, each shape gets its OWN gap size / capacity /
    adjacency / ordering (a 32x32x8 gap genuinely differs from a 16x16x16 gap);
    the per-WIDTH capacity (b32 vs b128) is emitted even for a single shape since
    that split is new signal regardless. Per-shape conflict groups fire on the
    same rule as the pooled one, but scoped to a shape's own numbers."""
    by_class = _pool_quant_by_class(quants)
    multi = len(by_class) > 1
    cons: List[Dict] = []
    cgroups: List[List[str]] = []
    for cls in sorted(by_class):
        o = by_class[cls]
        cap_median: Dict[str, float] = {}
        coc_rate: Dict[str, float] = {}
        if multi:
            gst = _stats(o["gap"])
            if gst:
                cons.append({"metric": "mfma_gap_size", "mfma_class": cls,
                             "stat": gst, "weight": _support_weight(n_k)})
            for k in sorted(o["cap"]):
                st = _stats(o["cap"][k])
                if st:
                    cap_median[k] = st["median"]
                    cons.append({"metric": "per_slot_capacity", "kind": k,
                                 "mfma_class": cls, "stat": st,
                                 "weight": _support_weight(o["support"][k])})
            for k in sorted(o["coc_either"]):
                either = o["coc_either"][k]
                if not either:
                    continue
                rate = round(o["coc_both"][k] / either, 2)
                coc_rate[k] = rate
                cons.append({
                    "metric": "adjacent_cooccur", "kind": k, "mfma_class": cls,
                    "value": rate, "polarity": "avoid" if rate <= 0.34 else "ok",
                    "n_pairs": o["coc_pairs"][k],
                    "weight": _support_weight(n_k, 1.0 - rate if rate <= 0.34 else rate)})
            for (a, b), both in sorted(o["order_both"].items()):
                if both < 2:
                    continue
                freq = o["order_before"][(a, b)] / both
                if freq >= 0.7:
                    cons.append({"metric": "intra_gap_order", "before": a, "after": b,
                                 "mfma_class": cls, "freq": round(freq, 2),
                                 "weight": _support_weight(n_k, freq)})
            # per-shape conflict group: pack many/slot vs avoid adjacent, scoped
            # to THIS shape's measured numbers.
            for k in sorted(cap_median):
                if cap_median[k] >= 2 and coc_rate.get(k, 1.0) <= 0.34:
                    cgroups.append(["per_slot_capacity@%s:%s" % (cls, k),
                                    "adjacent_cooccur@%s:%s" % (cls, k)])
        for (k, w) in sorted(o["cap_w"]):
            st = _stats(o["cap_w"][(k, w)])
            if st:
                cons.append({"metric": "per_slot_capacity", "kind": k,
                             "mfma_class": cls, "width": w, "stat": st,
                             "weight": _support_weight(o["w_support"][(k, w)])})
    return cons, cgroups


def build_quant_skills(records: List[Dict]) -> List[Skill]:
    groups: Dict[Tuple[str, str, str], List[Tuple[str, Dict]]] = defaultdict(list)
    for rec in records:
        for rr in rec["regions"]:
            q = rr["signature"].get("quant")
            if q:
                key = (rec["arch"], rec["kernel_class"], rr["kind"])
                groups[key].append((rec["name"], q))

    skills: List[Skill] = []
    for (arch, kernel_class, region_kind), items in sorted(groups.items()):
        kernels = sorted({name for name, _ in items})
        n_k = len(kernels)
        pooled = _pool_quant([q for _, q in items])

        constraints: List[Dict] = []
        gap_stats = _stats(pooled["gap_raw"])
        if gap_stats:
            constraints.append({"metric": "mfma_gap_size", "stat": gap_stats,
                                "weight": _support_weight(n_k)})

        cap_stats: Dict[str, Dict] = {}
        for k, raw in sorted(pooled["cap_raw"].items()):
            st = _stats(raw)
            cap_stats[k] = st
            constraints.append({
                "metric": "per_slot_capacity", "kind": k, "stat": st,
                "weight": _support_weight(pooled["cap_support"][k])})

        for k, raw in sorted(pooled["burst_raw"].items()):
            constraints.append({"metric": "burst_runlen", "kind": k,
                                "stat": _stats(raw), "weight": _support_weight(n_k)})

        coc_rate: Dict[str, float] = {}
        for k in sorted(pooled["coc_either"]):
            either = pooled["coc_either"][k]
            if not either:
                continue
            rate = round(pooled["coc_both"][k] / either, 2)
            coc_rate[k] = rate
            constraints.append({
                "metric": "adjacent_cooccur", "kind": k, "value": rate,
                "polarity": "avoid" if rate <= 0.34 else "ok",
                "n_pairs": pooled["coc_pairs"][k],
                "weight": _support_weight(n_k, 1.0 - rate if rate <= 0.34 else rate)})

        for (a, b), both in sorted(pooled["order_both"].items()):
            if both < 2:
                continue
            freq = pooled["order_before"][(a, b)] / both
            if freq >= 0.7:
                constraints.append({"metric": "intra_gap_order", "before": a,
                                    "after": b, "freq": round(freq, 2),
                                    "weight": _support_weight(n_k, freq)})

        # per-MFMA-shape + per-width refinements (the "one mfma / one lds" fix):
        # sized placement reads these, the pooled constraints above stay the
        # canonical scoring set.
        class_cons, class_cgroups = _class_constraints([q for _, q in items], n_k)
        constraints.extend(class_cons)

        # conflict groups: a high per-slot capacity for a kind that ALSO rarely
        # co-occurs in adjacent slots is the canonical tension (pack many per
        # slot vs. don't fill neighbours) the agent must weigh per target kernel.
        conflict_groups: List[List[str]] = []
        for k, st in cap_stats.items():
            if st and st["median"] >= 2 and coc_rate.get(k, 1.0) <= 0.34:
                conflict_groups.append(["per_slot_capacity:%s" % k,
                                        "adjacent_cooccur:%s" % k])
        conflict_groups.extend(class_cgroups)   # per-MFMA-shape tensions

        if not constraints:
            continue
        avg_w = round(statistics.fmean(c["weight"] for c in constraints), 3)
        action: Dict = {"constraints": constraints}
        if conflict_groups:
            action["conflict_groups"] = conflict_groups
        gs = "gap~%s" % (gap_stats["median"] if gap_stats else "?")
        skills.append(Skill(
            id="gold-%s-%s-quant" % (kernel_class, region_kind),
            statement="[gold-mined, static-quant] %s/%s layout: MFMA %s, %d measured constraints%s"
                      % (kernel_class, region_kind, gs, len(constraints),
                         " (with %d conflict group/s)" % len(conflict_groups)
                         if conflict_groups else ""),
            when={"arch": arch, "loop_kind": kernel_class, "region": region_kind},
            action=action,
            evidence={"kernels": kernels, "n_samples": n_k,
                      "source": "gold_corpus(modeA-quant)"},
            effect={"note": "measured layout ranges; unvalidated -- agent weighs + HW-checks"},
            confidence=avg_w,
            status="candidate",
        ))
    return skills


# ---------------------------------------------------------------------------
# Reporting + persistence
# ---------------------------------------------------------------------------
def render_report(records: List[Dict], skills: List[Skill]) -> str:
    lines = ["# gold corpus mining report (Mode A, static)", ""]
    lines.append("- kernels: %d" % len(records))
    lines.append("- candidate skills: %d (status=candidate; promote manually after review)" % len(skills))
    lines.append("")
    lines.append("## per-kernel classification")
    lines.append("")
    lines.append("| kernel | arch | kernel_class | regions |")
    lines.append("|---|---|---|---|")
    for rec in records:
        rkinds = ", ".join("%s(%d)" % (rr["kind"], rr["signature"]["n_instr"])
                           for rr in rec["regions"])
        lines.append("| %s | %s | %s | %s |"
                     % (rec["name"], rec["arch"], rec["kernel_class"], rkinds))
    lines.append("")
    lines.append("## candidate skills (by arch / kernel_class / region)")
    lines.append("")
    for s in sorted(skills, key=lambda x: x.id):
        if "specs" not in s.action:        # quant-constraint skills get their own section
            continue
        specs = ", ".join(kn._transform_id(sp) for sp in s.action.get("specs", []))
        lines.append("### `%s`  (confidence=%.2f, n=%d)" % (
            s.id, s.confidence, s.evidence.get("n_samples", 0)))
        lines.append("- when: `%s`" % json.dumps(s.when, sort_keys=True))
        lines.append("- specs: %s" % specs)
        if s.action.get("note"):
            lines.append("- note: %s" % s.action["note"])
        lines.append("- evidence kernels: %s" % ", ".join(s.evidence.get("kernels", [])))
        lines.append("")

    quant = [s for s in skills if "constraints" in s.action]
    if quant:
        lines.append("## fine-grained quant layout skills (measured ranges)")
        lines.append("")
        lines.append("Each number is POOLED from the gold corpus; the agent reads")
        lines.append("these as weighted constraints (and weighs conflict_groups) when")
        lines.append("laying out a fresh kernel, then validates on hardware.")
        lines.append("")
        for s in sorted(quant, key=lambda x: x.id):
            lines.append("### `%s`  (confidence=%.2f, n=%d)" % (
                s.id, s.confidence, s.evidence.get("n_samples", 0)))
            lines.append("- when: `%s`" % json.dumps(s.when, sort_keys=True))
            for c in s.action["constraints"]:
                lines.append("  - %s" % _fmt_constraint(c))
            for g in s.action.get("conflict_groups", []):
                lines.append("  - CONFLICT: %s (agent must weigh per target kernel)"
                             % " vs ".join(g))
            lines.append("- evidence kernels: %s" % ", ".join(s.evidence.get("kernels", [])))
            lines.append("")

    cls_section = _render_mfma_class_breakdown(records)
    if cls_section:
        lines.extend(cls_section)
    return "\n".join(lines)


def _render_mfma_class_breakdown(records: List[Dict]) -> List[str]:
    """Per-(arch/kernel_class/region) gap + filler-capacity table, BROKEN OUT by
    MFMA shape (and access width). This is the human-checkable evidence that the
    finer model is real: distinct shapes should show distinct gap sizes."""
    # group like build_quant_skills, pool by_mfma_class across kernels.
    groups: Dict[Tuple[str, str, str], List[Dict]] = defaultdict(list)
    for rec in records:
        for rr in rec["regions"]:
            q = rr["signature"].get("quant")
            if q and q.get("by_mfma_class"):
                groups[(rec["arch"], rec["kernel_class"], rr["kind"])].append(q)
    if not groups:
        return []

    out = ["## per-MFMA-class gap breakdown (measured)", "",
           "Gaps are bucketed by the SHAPE of the MFMA that opens them: different",
           "shapes have different result latency, so they open different-sized gaps",
           "that hold different filler counts. Capacity is split by access width.",
           ""]
    for (arch, kclass, region), quants in sorted(groups.items()):
        # pool: class -> {"gap": [...], "cap": {kind: {width|"*": [...]}}}
        pool: Dict[str, Dict] = defaultdict(
            lambda: {"gap": [], "cap": defaultdict(lambda: defaultdict(list))})
        for q in quants:
            for cls, m in q["by_mfma_class"].items():
                pool[cls]["gap"].extend(m["mfma_gap_size"]["raw"])
                for k, cap in m.get("per_slot_capacity", {}).items():
                    pool[cls]["cap"][k]["*"].extend(cap["raw"])
                    for w, wc in cap.get("by_width", {}).items():
                        pool[cls]["cap"][k][w].extend(wc["raw"])
        out.append("### `%s` / `%s` / `%s`" % (arch, kclass, region))
        out.append("")
        out.append("| MFMA shape | n_gaps | gap median [min..max] | filler capacity median/max per gap (by width: max) |")
        out.append("|---|---|---|---|")
        for cls in sorted(pool):
            gst = _stats(pool[cls]["gap"])
            caps = []
            for k in sorted(pool[cls]["cap"]):
                widths = pool[cls]["cap"][k]
                star = _stats(widths.get("*", []))
                if not star or not star["max"]:
                    continue
                label = "%s=%s/%s" % (k, star["median"], star["max"])
                # per-width MAX makes b128 vs b32 visible even when a typical gap
                # holds 0 of the kind (LDS reads cluster -> median often 0).
                wparts = ["%s:%s" % (w, _stats(v)["max"])
                          for w, v in sorted(widths.items())
                          if w != "*" and _stats(v) and _stats(v)["max"]]
                if wparts:
                    label += " (" + ", ".join(wparts) + ")"
                caps.append(label)
            out.append("| %s | %d | %s [%s..%s] | %s |" % (
                cls, gst["n"] if gst else 0,
                gst["median"] if gst else "?", gst["min"] if gst else "?",
                gst["max"] if gst else "?", ", ".join(caps) or "-"))
        out.append("")
    return out


def _fmt_constraint(c: Dict) -> str:
    m = c["metric"]
    w = c.get("weight")
    cls = (" @%s" % c["mfma_class"]) if c.get("mfma_class") else ""
    if m == "mfma_gap_size":
        st = c["stat"]
        return "mfma_gap_size%s: median=%s [%s..%s] (w=%s)" % (
            cls, st["median"], st["min"], st["max"], w)
    if m == "per_slot_capacity":
        st = c["stat"]
        width = ("/%s" % c["width"]) if c.get("width") else ""
        return "per_slot_capacity[%s%s]%s: median=%s max=%s (w=%s)" % (
            c["kind"], width, cls, st["median"], st["max"], w)
    if m == "burst_runlen":
        st = c["stat"]
        return "burst_runlen[%s]: median=%s max=%s (w=%s)" % (
            c["kind"], st["median"], st["max"], w)
    if m == "adjacent_cooccur":
        return "adjacent_cooccur[%s]%s: rate=%s polarity=%s (w=%s)" % (
            c["kind"], cls, c["value"], c["polarity"], w)
    if m == "intra_gap_order":
        return "intra_gap_order%s: %s before %s (freq=%s, w=%s)" % (
            cls, c["before"], c["after"], c["freq"], w)
    return json.dumps(c, sort_keys=True)


def write_outputs(records: List[Dict], skills: List[Skill], out_store: str) -> Dict:
    for s in skills:
        kn.save_skill(s, out_store)   # -> <out_store>/skills/<id>.json
    report = render_report(records, skills)
    report_path = os.path.join(out_store, "mine_report.md")
    os.makedirs(out_store, exist_ok=True)
    with open(report_path, "w") as fh:
        fh.write(report)
    return {"skills_dir": kn._skills_dir(out_store), "report": report_path}


def _arg(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    corpus = _arg(argv, "--corpus", DEFAULT_CORPUS)
    out_store = _arg(argv, "--out", DEFAULT_OUT)

    if not os.path.isdir(corpus):
        sys.stderr.write(
            "[mine] corpus dir not found: %s\n"
            "       create it (one subdir per kernel with a .s, optional meta.json)\n"
            "       or pass --corpus PATH.\n" % corpus)
        return 2

    records = mine_corpus(corpus)
    if not records:
        sys.stderr.write("[mine] no kernels found under %s\n" % corpus)
        return 2
    skills = build_skills(records) + build_quant_skills(records)
    paths = write_outputs(records, skills, out_store)

    print("[mine] kernels=%d  candidate_skills=%d" % (len(records), len(skills)))
    print("[mine] skills : %s" % paths["skills_dir"])
    print("[mine] report : %s" % paths["report"])
    for s in sorted(skills, key=lambda x: x.id):
        print("  [candidate c=%.2f] %s -> %s" % (
            s.confidence, json.dumps(s.when, sort_keys=True),
            ", ".join(kn._transform_id(sp) for sp in s.action.get("specs", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
