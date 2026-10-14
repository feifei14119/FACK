"""Layer 2 (offline AI articulation) -- STAGE 2 / ingest + validate.

Read the AI agent's ``ai_proposal.json`` (written against ``ai_brief.json`` by
``ai_skill_brief.py``) and turn it into CANDIDATE skills -- but only after a
strict, deterministic gate that makes it impossible for the agent to pollute
the store. The AI may articulate and extrapolate; it may NOT invent measured
numbers or widen scope.

Gate (per proposed skill / constraint):
  * scope is taken from the cited group (arch/kernel_class/region) -- the agent
    cannot add a shape / kernel name / new key;
  * a constraint with ``extrapolated=false`` is matched by reference to a Layer-1
    measured constraint; the AUTHORITATIVE number is copied from the brief (the
    agent's echoed number is ignored, only warned on if it disagrees). No match
    => dropped (a hallucinated "measured" rule cannot enter);
  * a constraint with ``extrapolated=true`` must carry a non-empty note; it is
    admitted but its weight is capped (EXTRAP_CAP) and tagged source=ai-hypothesis;
  * confidence is capped (<= the gold quant skill) so seed_search_plan de-dup
    always keeps the MEASURED constraint over an AI restatement;
  * status is always ``candidate`` -- only hardware (validate_skills.py /
    AgentSession.learn_layouts(validate=True)) promotes to trusted.

  python3.8 tools/ingest_ai_skills.py [--out DIR] [--proposal FILE] [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn
from agent.knowledge import Skill

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO, "study_case", "study_out")

EXTRAP_CAP = 0.3       # ceiling for an extrapolated (unmeasured) constraint/skill
MEASURED_AI_CAP = 0.6  # ceiling for a measured-only AI restatement (< gold ~0.89)
AI_SOURCE = "gold_corpus(modeB-ai)"

# scope keys the agent is allowed to keep (structural only -- red line).
_ALLOWED_SCOPE = frozenset({"arch", "loop_kind", "region"})


def _num_fields(c: Dict) -> Dict[str, float]:
    """The numbers an agent might (wrongly) try to restate for a measured rule."""
    m = c.get("metric")
    if m in ("mfma_gap_size", "per_slot_capacity", "burst_runlen"):
        st = c.get("stat", {}) or {}
        return {k: st[k] for k in ("median", "max") if k in st}
    if m == "adjacent_cooccur":
        return {k: c[k] for k in ("value",) if k in c}
    if m == "intra_gap_order":
        return {k: c[k] for k in ("freq",) if k in c}
    return {}


def _disagrees(proposed: Dict, authoritative: Dict) -> bool:
    pn = _num_fields(proposed)
    an = _num_fields(authoritative)
    for k, v in pn.items():
        if k in an and abs(float(v) - float(an[k])) > 0.01:
            return True
    return False


class _GroupIndex:
    def __init__(self, group: Dict):
        self.scope = {k: v for k, v in group.get("scope", {}).items()
                      if k in _ALLOWED_SCOPE}
        self.n_samples = group.get("n_samples")
        self.kernels = group.get("kernels", [])
        self.base_confidence = group.get("base_confidence", 0.0)
        self.base_skill_id = group.get("base_skill_id")
        self.by_ref = {kn._constraint_id(c): c for c in group.get("measured", [])}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "-", str(s).lower()).strip("-_") or "ai"


def validate_proposal(proposal: Dict, brief: Dict
                      ) -> Tuple[List[Skill], List[str]]:
    """Pure validator: (skills, warnings). Never writes. Drops anything that
    violates the gate; warnings explain every drop/clamp."""
    groups = {g["base_skill_id"]: _GroupIndex(g) for g in brief.get("groups", [])}
    warns: List[str] = []
    skills: List[Skill] = []

    for i, prop in enumerate(proposal.get("skills", [])):
        tag = prop.get("id_suffix") or "ai%d" % i
        base_id = prop.get("base_skill_id")
        gi = groups.get(base_id)
        if gi is None:
            warns.append("skill[%s]: unknown base_skill_id %r -- dropped"
                         % (tag, base_id))
            continue

        kept: List[Dict] = []
        any_extrap = False
        for c in prop.get("constraints", []):
            extrap = bool(c.get("extrapolated"))
            if not extrap:
                ref = kn._constraint_id(c)
                auth = gi.by_ref.get(ref)
                if auth is None:
                    warns.append("skill[%s]: constraint %r claims measured but no "
                                 "such Layer-1 ref -- dropped" % (tag, ref))
                    continue
                if _disagrees(c, auth):
                    warns.append("skill[%s]: constraint %r restated a measured "
                                 "number; using authoritative Layer-1 value" % (tag, ref))
                out = dict(auth)  # AUTHORITATIVE copy -- agent cannot alter numbers
                w = c.get("weight", out.get("weight", 0.9))
                out["weight"] = round(min(float(w), float(out.get("weight", 0.9))), 3)
                out["source"] = "measured"
                kept.append(out)
            else:
                note = (c.get("note") or "").strip()
                if not note:
                    warns.append("skill[%s]: extrapolated constraint without a "
                                 "note -- dropped" % tag)
                    continue
                w = round(min(float(c.get("weight", EXTRAP_CAP)), EXTRAP_CAP), 3)
                out = {"metric": c.get("metric", "hint"), "note": note,
                       "weight": w, "extrapolated": True, "source": "ai-hypothesis"}
                for opt in ("kind", "before", "after", "mfma_class", "width"):
                    if c.get(opt) is not None:
                        out[opt] = c[opt]
                kept.append(out)
                any_extrap = True

        if not kept:
            warns.append("skill[%s]: no admissible constraints -- dropped" % tag)
            continue

        # conflict groups: keep only those whose members all resolve to a kept
        # or measured constraint ref.
        kept_refs = {kn._constraint_id(c) for c in kept} | set(gi.by_ref)
        cgroups: List[List[str]] = []
        for grp in prop.get("conflict_groups", []):
            if all(m in kept_refs for m in grp):
                cgroups.append(list(grp))
            else:
                warns.append("skill[%s]: conflict_group %s has unresolved members "
                             "-- dropped" % (tag, grp))

        cap = EXTRAP_CAP if any_extrap else MEASURED_AI_CAP
        conf = round(min(cap, float(gi.base_confidence)), 3)
        action: Dict = {"constraints": kept}
        if cgroups:
            action["conflict_groups"] = cgroups
        if prop.get("rationale"):
            action["note"] = prop["rationale"]
        sid = "ai-%s-%s-%s" % (_slug(gi.scope.get("loop_kind", "any")),
                               _slug(gi.scope.get("region", "any")), _slug(tag))
        n_meas = sum(1 for c in kept if not c.get("extrapolated"))
        n_ext = len(kept) - n_meas
        skills.append(Skill(
            id=sid,
            statement=prop.get("statement")
            or "[ai-articulated] %s/%s: %d measured + %d extrapolated constraint/s"
            % (gi.scope.get("loop_kind"), gi.scope.get("region"), n_meas, n_ext),
            when=dict(gi.scope),
            action=action,
            evidence={"source": AI_SOURCE, "based_on": gi.base_skill_id,
                      "n_samples": gi.n_samples, "kernels": gi.kernels},
            effect={"note": "ai-articulated; UNVALIDATED (esp. extrapolated rules) "
                            "-- hardware must adjudicate before trust"},
            confidence=conf,
            status="candidate",
        ))
    return skills, warns


# ---------------------------------------------------------------------------
# Human-readable rendering -- so an engineer can judge an AI skill's validity
# (and learn from it) WITHOUT reading JSON. Rendered DETERMINISTICALLY from the
# already-gated skills, so it can never drift from what actually landed: measured
# numbers are the Layer-1 authoritative values, extrapolations are clearly marked
# UNVALIDATED. The AI's own one-line statement + rationale ride along too.
# ---------------------------------------------------------------------------
_POLARITY_CN = {"avoid": "建议规避相邻", "ok": "可相邻共存"}


def _fmt_ai_constraint(c: Dict) -> str:
    m = c.get("metric")
    w = c.get("weight")
    cls = ("·MFMA %s" % c["mfma_class"]) if c.get("mfma_class") else ""
    if c.get("extrapolated"):
        kind = (" [%s]" % c["kind"]) if c.get("kind") else ""
        return "- 💡 **外推%s%s**(未验证·AI 假设,权重 %s):%s" % (kind, cls, w, c.get("note", ""))
    if m == "mfma_gap_size":
        st = c.get("stat", {})
        return ("- 📏 **MFMA 间隙大小%s**:中位 %s,范围 [%s..%s],p75 %s(权重 %s)"
                % (cls, st.get("median"), st.get("min"), st.get("max"), st.get("p75"), w))
    if m == "per_slot_capacity":
        st = c.get("stat", {})
        width = ("/%s" % c["width"]) if c.get("width") else ""
        return ("- 📦 **每槽容量[%s%s]%s**:中位 %s,上限 %s(权重 %s)"
                % (c.get("kind"), width, cls, st.get("median"), st.get("max"), w))
    if m == "burst_runlen":
        st = c.get("stat", {})
        return ("- 🔁 **连发长度[%s]**:中位 %s,上限 %s(权重 %s)"
                % (c.get("kind"), st.get("median"), st.get("max"), w))
    if m == "adjacent_cooccur":
        return ("- 🔗 **相邻共现[%s]%s**:比例 %s → %s(权重 %s)"
                % (c.get("kind"), cls, c.get("value"),
                   _POLARITY_CN.get(c.get("polarity"), c.get("polarity")), w))
    if m == "intra_gap_order":
        return ("- ➡️ **间隙内顺序%s**:%s 先于 %s(频率 %s,权重 %s)"
                % (cls, c.get("before"), c.get("after"), c.get("freq"), w))
    return "- %s(权重 %s)" % (json.dumps(c, ensure_ascii=False, sort_keys=True), w)


def render_ai_skills_md(skills: List[Skill]) -> str:
    L: List[str] = [
        "# AI 归纳技能(人类可读)", "",
        "> 由 `tools/ingest_ai_skills.py` 在摄入时**确定性生成**,与 `skills/ai-*.json` 一一对应。",
        "> 供工程师审阅有效性、学习其调度直觉。**实测项**的数字来自 gold 语料(Layer 1 权威,可信);",
        "> **外推项(💡)** 是 AI 基于实测提出的假设,**未经真机验证**,低权重、低置信,真机佐证后才可能晋升。", "",
        "- 技能数:%d" % len(skills),
        "- 状态一律 `candidate`(永不自动晋升);真机验证见 `tools/validate_skills.py` / `mine_skills.sh::VALIDATE`。", "",
        "---", "",
    ]
    if not skills:
        L.append("(本次没有通过闸门的 AI 技能。)")
        return "\n".join(L)
    for s in sorted(skills, key=lambda x: x.id):
        cons = s.action.get("constraints", [])
        measured = [c for c in cons if not c.get("extrapolated")]
        extrap = [c for c in cons if c.get("extrapolated")]
        L.append("## `%s`" % s.id)
        L.append("")
        L.append("**%s**" % s.statement)
        L.append("")
        L.append("- 置信度 `%.2f` · 状态 `%s` · 来源 `%s` · 基于 `%s`(%s 个 kernel 实测)"
                 % (s.confidence, s.status, s.evidence.get("source"),
                    s.evidence.get("based_on"), s.evidence.get("n_samples")))
        L.append("- 适用范围:`%s`" % json.dumps(s.when, ensure_ascii=False, sort_keys=True))
        L.append("")
        if s.action.get("note"):
            L.append("**AI 归因(rationale)**:%s" % s.action["note"])
            L.append("")
        L.append("**实测约束(Layer 1,权威可信,共 %d 条)**:" % len(measured))
        L.append("")
        L.extend(_fmt_ai_constraint(c) for c in measured)
        L.append("")
        if extrap:
            L.append("**AI 外推(未验证,需真机佐证,共 %d 条)**:" % len(extrap))
            L.append("")
            L.extend(_fmt_ai_constraint(c) for c in extrap)
            L.append("")
        for grp in s.action.get("conflict_groups", []):
            L.append("**冲突权衡**:`%s` —— 需按目标 kernel 资源逐一权衡(打包 vs 摊开)。"
                     % "` ⟷ `".join(grp))
            L.append("")
        L.append("---")
        L.append("")
    return "\n".join(L)


def _arg(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    store = _arg(argv, "--out", DEFAULT_OUT)
    proposal_path = _arg(argv, "--proposal",
                         os.path.join(store, "ai_proposal.json"))
    brief_path = _arg(argv, "--brief", os.path.join(store, "ai_brief.json"))
    dry = "--dry-run" in argv

    for p, what in ((brief_path, "brief"), (proposal_path, "proposal")):
        if not os.path.isfile(p):
            sys.stderr.write("[ingest] %s not found: %s\n" % (what, p))
            return 2
    with open(brief_path) as fh:
        brief = json.load(fh)
    with open(proposal_path) as fh:
        proposal = json.load(fh)

    skills, warns = validate_proposal(proposal, brief)
    for w in warns:
        print("[ingest][warn] %s" % w)
    print("[ingest] admitted %d AI skill/s (%d proposed)"
          % (len(skills), len(proposal.get("skills", []))))
    for s in skills:
        n_ext = sum(1 for c in s.action["constraints"] if c.get("extrapolated"))
        print("  [candidate c=%.2f] %s  (%d constraints, %d extrapolated)%s"
              % (s.confidence, s.id, len(s.action["constraints"]), n_ext,
                 "  conflict_groups=%d" % len(s.action["conflict_groups"])
                 if "conflict_groups" in s.action else ""))
    if dry:
        print("[ingest] --dry-run: nothing written")
        return 0
    for s in skills:
        kn.save_skill(s, store)
    md_path = os.path.join(store, "ai_skills.md")
    with open(md_path, "w") as fh:
        fh.write(render_ai_skills_md(skills))
    if skills:
        print("[ingest] wrote -> %s" % kn._skills_dir(store))
    print("[ingest] human-readable -> %s" % md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
