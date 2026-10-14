"""Meta-layer knowledge / memory for the tuner (M7).

Core safety principle (see proj/knowledge_agent_design.md §2):

    Knowledge only NAVIGATES (what to TRY first), it never ADJUDICATES
    legality (what is VALID). Legality is hard-coded in the engine + compile /
    numerical tests + the Verifier. Even a wrong skill can only waste search
    budget -- it can NEVER produce a bad kernel.

This module is the *meta layer*, invoked at low frequency around the fixed-logic
search (which stays pure and reproducible):

  * BEFORE tuning  -- ``seed_search_plan``: read the skill store (+ optional ISA
    notes) and emit an ORDERED list of candidate transform specs (a prior) for
    a kernel context. These specs are exactly the ``build_candidate`` specs the
    search driver already understands, so the plan just re-orders what to try
    first; the search still gates every candidate by correctness + Verifier +
    the measured-GFLOPS noise margin.
  * DURING tuning  -- nothing here; the inner loop is fixed logic.
  * AFTER tuning   -- ``log_experiment`` records structured evidence and
    ``induce_skills`` generalises it into candidate/trusted skills (with
    evidence, effect size, confidence, scope, and a promotion gate).

Persistence is plain files (cross-session memory = files, per the design):
``<store>/skills/*.json`` and ``<store>/experiments.log`` (JSONL).
"""
from __future__ import annotations

import json
import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

DEFAULT_STORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge", "engine")

# Curated, human-reviewed knowledge lives in DEFAULT_STORE (knowledge/engine,
# see knowledge/README.md) and is READ at seed
# time (load_skills / seed_search_plan). All RUNTIME outputs -- the raw
# experiments log and freshly INDUCED skills -- are written to the tuning
# client's ``client/<name>/tune_out`` (``client.Client.out_dir``), so a tuning
# run never mutates the code tree / curated store. DEFAULT_OUT_STORE is only the
# fallback for runs without a client (CPU-only observe, library use). Promote
# reviewed skills into knowledge/engine/skills manually. See knowledge/README.md.
DEFAULT_OUT_STORE = os.path.join(tempfile.gettempdir(), "fack_tune_out")


# ---------------------------------------------------------------------------
# Skill schema -- every skill carries evidence + confidence + scope + status so
# self-evolution cannot silently pollute the store (design §5).
# ---------------------------------------------------------------------------
@dataclass
class Skill:
    id: str
    statement: str                       # human-readable heuristic
    when: Dict = field(default_factory=dict)     # scope/applicability filter
    action: Dict = field(default_factory=dict)   # {"specs":[...]} | {"avoid":[...]} | {"note":...}
    evidence: Dict = field(default_factory=dict)  # {kernels:[...], shapes:[...], n_samples:int}
    effect: Dict = field(default_factory=dict)    # {mean_delta:float, win_rate:"k/n"}
    confidence: float = 0.0
    status: str = "candidate"            # "candidate" -> "trusted"

    def applies(self, context: Dict) -> bool:
        """A skill applies when every key it constrains matches the context.
        Missing keys in ``when`` are wildcards (broadest scope)."""
        for k, v in self.when.items():
            if context.get(k) != v:
                return False
        return True


# ---------------------------------------------------------------------------
# Store I/O
# ---------------------------------------------------------------------------
def _skills_dir(store: str) -> str:
    return os.path.join(store, "skills")


def _log_path(store: str) -> str:
    return os.path.join(store, "experiments.log")


def load_skills(store: str = DEFAULT_STORE) -> List[Skill]:
    d = _skills_dir(store)
    if not os.path.isdir(d):
        return []
    out: List[Skill] = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            with open(os.path.join(d, fn)) as f:
                out.append(Skill(**json.load(f)))
    return out


def save_skill(skill: Skill, store: str = DEFAULT_OUT_STORE) -> str:
    d = _skills_dir(store)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s.json" % skill.id)
    with open(p, "w") as f:
        json.dump(asdict(skill), f, indent=2, sort_keys=True)
    return p


def log_experiment(record: Dict, store: str = DEFAULT_OUT_STORE) -> None:
    """Append one structured trial to the experiments log (the raw memory).

    Expected keys: kernel, shape, arch, loop_kind, scenario, bottleneck,
    transform (a build_candidate spec or {"kind":"ladder"} baseline),
    baseline_tflops, tflops, correct. ``delta`` is derived if absent."""
    os.makedirs(store, exist_ok=True)
    rec = dict(record)
    if "delta" not in rec and rec.get("tflops") and rec.get("baseline_tflops"):
        rec["delta"] = rec["tflops"] / rec["baseline_tflops"] - 1.0
    with open(_log_path(store), "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def read_experiments(store: str = DEFAULT_OUT_STORE) -> List[Dict]:
    p = _log_path(store)
    if not os.path.isfile(p):
        return []
    out = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# Translate a skill / spec into the 4 engine landing forms (design §3). For now
# the actionable form is the build_candidate spec list; constraints/weights ride
# inside the spec (e.g. listsched Weights) -- the search consumes them directly.
# ---------------------------------------------------------------------------
def _transform_id(spec: Dict) -> str:
    """Stable signature for grouping equivalent transforms in the log."""
    kind = spec.get("kind", "?")
    if kind in ("layout", "order"):
        # Instruction IDs only identify an intent within its parent version.
        # Do not collapse every explicit layout/order into a global failure.
        return kind + ":" + hashlib.sha256(json.dumps(
            spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if kind == "compact":
        return "compact:%s:%s" % (spec.get("reorder_kind"), spec.get("earliest"))
    if kind == "listsched":
        w = spec.get("weights")
        if isinstance(w, dict):
            wid = ",".join("%s=%s" % (k, w[k]) for k in sorted(w))
        elif w is not None:
            wid = repr(w)
        else:
            wid = "default"
        return "listsched:%s" % wid
    if kind == "ladder":
        return "ladder:%s" % spec.get("level")
    return kind


def _constraint_id(c: Dict) -> str:
    """Stable signature for de-duping a fine-grained layout constraint across
    skills (used when merging quant skills in seed_search_plan, and as the brief
    <-> proposal reference in Layer 2). An optional MFMA shape (``mfma_class``)
    and access ``width`` refine the id so a per-shape / per-width constraint does
    not collide with the pooled one; both absent => the historical id is unchanged."""
    metric = c.get("metric", "?")
    cls = c.get("mfma_class")
    base = "%s@%s" % (metric, cls) if cls else metric
    if metric == "intra_gap_order":
        return "%s:%s>%s" % (base, c.get("before"), c.get("after"))
    kind = c.get("kind")
    if not kind:
        return base
    width = c.get("width")
    return "%s:%s/%s" % (base, kind, width) if width else "%s:%s" % (base, kind)


# ---------------------------------------------------------------------------
# BEFORE tuning: seed an ordered candidate plan from trusted-first skills.
# ---------------------------------------------------------------------------
def seed_search_plan(context: Dict, store: str = DEFAULT_STORE,
                     isa_notes_dir: Optional[str] = None) -> Dict:
    """Read the skill store and emit a prior PLAN for a kernel ``context``
    (e.g. ``{"arch":"gfx942","loop_kind":"mfma_dense","bottleneck":"compute",
    "scenario":"cold_start"}``).

    Returns ``{"specs": [...], "avoid": [...], "constraints": [...],
    "conflict_groups": [...], "notes": [...], "skills_used": [...]}`` --
    ``specs`` is an ordered build_candidate list to try FIRST (trusted skills
    before candidates, higher confidence first); ``avoid`` lists transform_ids
    known to regress; ``constraints``/``conflict_groups`` carry the gold-mined
    fine-grained layout ranges + weights + tensions (from quant skills) so the
    agent can weigh them when laying out a fresh kernel. This only NAVIGATES;
    the search still gates every candidate."""
    skills = [s for s in load_skills(store) if s.applies(context)]
    # trusted before candidate, then by confidence desc
    skills.sort(key=lambda s: (s.status != "trusted", -s.confidence))
    specs: List[Dict] = []
    avoid: List[str] = []
    notes: List[str] = []
    used: List[str] = []
    constraints: List[Dict] = []
    conflict_groups: List[List[str]] = []
    seen = set()
    seen_constraint = set()
    seen_group = set()
    for s in skills:
        used.append(s.id)
        for spec in s.action.get("specs", []):
            key = _transform_id(spec)
            if key not in seen:
                seen.add(key)
                specs.append(spec)
        for tid in s.action.get("avoid", []):
            if tid not in avoid:
                avoid.append(tid)
        for c in s.action.get("constraints", []):
            ckey = _constraint_id(c)
            if ckey not in seen_constraint:
                seen_constraint.add(ckey)
                constraints.append(c)
        for grp in s.action.get("conflict_groups", []):
            gkey = tuple(grp)
            if gkey not in seen_group:
                seen_group.add(gkey)
                conflict_groups.append(grp)
        if s.action.get("note"):
            notes.append(s.action["note"])
    if isa_notes_dir and os.path.isdir(isa_notes_dir):
        notes.append("isa_notes:%s" % isa_notes_dir)
    return {"specs": specs, "avoid": avoid, "constraints": constraints,
            "conflict_groups": conflict_groups, "notes": notes,
            "skills_used": used}


# ---------------------------------------------------------------------------
# AFTER tuning: induce candidate/trusted skills from the experiments log.
# ---------------------------------------------------------------------------
def induce_skills(store: str = DEFAULT_OUT_STORE, *, min_samples: int = 3,
                  win_margin: float = 0.01, min_win_rate: float = 0.6,
                  trust_distinct_kernels: int = 2) -> List[Skill]:
    """Generalise the experiments log into skills, one per
    (arch, loop_kind, bottleneck, transform). Computes effect size + win rate +
    sample count; promotes to ``trusted`` only when corroborated across enough
    INDEPENDENT kernels (the anti-pollution gate, design §5).

    A transform with positive mean_delta becomes a "try this" skill (``specs``);
    a clearly-regressing one becomes an "avoid" skill -- both are navigation."""
    rows = [r for r in read_experiments(store)
            if r.get("transform", {}).get("kind") not in (None, "ladder")
            # No candidate performance was established by these outcomes.
            # Keep them in the log, but never teach a performance "avoid".
            and r.get("verdict") not in (
                "illegal", "baseline_failed", "compile_failed", "measurement_invalid")]
    groups: Dict[tuple, List[Dict]] = {}
    for r in rows:
        if r["transform"].get("kind") in ("layout", "order"):
            # These raw IDs cannot be generalized across kernels. Detailed
            # failures remain in the run ledger; no broad prefer/avoid skill
            # may be induced from legacy logs missing versioned provenance.
            continue
        key = (r.get("arch"), r.get("loop_kind"), r.get("bottleneck"),
               r.get("scenario"), r.get("region"), _transform_id(r["transform"]))
        groups.setdefault(key, []).append(r)

    skills: List[Skill] = []
    for (arch, loop_kind, bottleneck, scenario, region_kind, tid), recs in sorted(
            groups.items(), key=lambda kv: str(kv[0])):
        n = len(recs)
        if n < 1:
            continue
        deltas = [r.get("delta", 0.0) for r in recs if r.get("correct")]
        n_correct = len(deltas)
        if n_correct == 0:
            mean_delta = -1.0          # always-incorrect transform: strong avoid
            wins = 0
        else:
            mean_delta = sum(deltas) / n_correct
            wins = sum(1 for d in deltas if d > win_margin)
        win_rate = wins / n if n else 0.0
        kernels = sorted({r.get("kernel") for r in recs if r.get("kernel")})
        shapes = sorted({r.get("shape") for r in recs if r.get("shape")})

        helpful = mean_delta > win_margin and win_rate >= min_win_rate
        sample_spec = recs[0]["transform"]
        scope = {k: v for k, v in
                 {"arch": arch, "loop_kind": loop_kind, "bottleneck": bottleneck,
                  "scenario": scenario, "region": region_kind}.items()
                 if v is not None}

        if helpful:
            action = {"specs": [sample_spec]}
            verb = "prefer"
        else:
            action = {"avoid": [tid]}
            verb = "avoid"
        # confidence rises with agreement (win-rate for prefer, loss-rate for
        # avoid) and sample count, capped < 1.
        agreement = win_rate if helpful else (1.0 - win_rate)
        confidence = round(min(0.95, agreement * (1 - 1.0 / (n + 1))), 3)
        trusted = (len(kernels) >= trust_distinct_kernels and n >= min_samples
                   and (win_rate >= min_win_rate if helpful else win_rate <= (1 - min_win_rate)))
        sid = "ind-%s-%s-%s-%s" % (scenario or "any", bottleneck or "any",
                                   loop_kind or "any", tid.replace(":", "_"))
        skills.append(Skill(
            id=sid,
            statement="%s transform %s on bottleneck=%s loop=%s (mean_delta=%+.1f%%)"
            % (verb, tid, bottleneck, loop_kind, 100 * mean_delta),
            when=scope,
            action=action,
            evidence={"kernels": kernels, "shapes": shapes, "n_samples": n},
            effect={"mean_delta": round(mean_delta, 4), "win_rate": "%d/%d" % (wins, n)},
            confidence=confidence,
            status="trusted" if trusted else "candidate",
        ))
    return skills


def induce_and_save(store: str = DEFAULT_OUT_STORE, **kw) -> List[Skill]:
    """Induce skills and persist them to the store (overwrites by id)."""
    skills = induce_skills(store, **kw)
    for s in skills:
        save_skill(s, store)
    return skills
