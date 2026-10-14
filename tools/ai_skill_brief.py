"""Layer 2 (offline AI articulation) -- STAGE 1 / export.

Pack the Layer-1 MEASURED constraint skills (``gold-*-quant.json``, produced by
``tools/mine_corpus.py``) into a compact, self-describing BRIEF that an external
AI agent reads to articulate richer, conditional, possibly EXTRAPOLATED skills.

Red lines baked into the brief (and re-enforced by ``ingest_ai_skills.py``):
  * the ``measured`` block is GROUND TRUTH -- the agent may select/re-weight it
    but must NEVER alter a measured number (Layer 1 owns the numbers);
  * any rule the agent adds beyond the measured ranges MUST be flagged
    ``extrapolated: true`` with a ``note`` -- it lands capped + low-confidence;
  * scope stays structural (arch / kernel_class / region); no shape, no kernel
    name -- the agent cannot widen or invent scope;
  * everything stays ``status=candidate`` -- only hardware promotes to trusted.

The AI is the EXTERNAL agent (no LLM client lives in this repo): this tool only
lays the deterministic rail IN, and ``ingest_ai_skills.py`` lays the rail OUT.

  python3.8 tools/ai_skill_brief.py [--out DIR]
      reads  <out>/skills/gold-*-quant.json
      writes <out>/ai_brief.json   (machine input for the agent + ingest)
             <out>/ai_brief.md     (human-readable copy of the same ask)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO, "study_case", "study_out")

QUANT_SOURCE = "gold_corpus(modeA-quant)"

REDLINES = [
    "measured numbers are GROUND TRUTH from Layer 1 -- never change them; "
    "to include one, reference it by (metric[,kind]) and it is copied verbatim.",
    "any rule beyond the measured ranges MUST set extrapolated=true and carry a "
    "non-empty note; it is admitted only capped + low-confidence.",
    "scope is fixed to the group's (arch,kernel_class,region) -- do NOT add a "
    "shape, a kernel name, or any other key.",
    "every articulated skill stays status=candidate; only hardware promotes it.",
]

ASK = (
    "For each group below, emit one or more articulated skills in ai_proposal.json "
    "(schema in ai_brief.md). Job: (1) SELECT the measured constraints that matter "
    "and assign a relative weight in (0,1]; (2) optionally add EXTRAPOLATED "
    "hypotheses (conditional/ordering rules implied by, but not present in, the "
    "measured data) flagged extrapolated=true + note; (3) declare conflict_groups "
    "(mutually-tense constraints the agent must trade off per target kernel); "
    "(4) write a one-line human statement + rationale."
)


def _is_quant_skill(s: kn.Skill) -> bool:
    return ("constraints" in s.action
            and s.evidence.get("source") == QUANT_SOURCE)


def build_brief(store: str) -> Dict:
    """Turn the measured quant skills under ``store`` into an AI brief dict."""
    groups: List[Dict] = []
    for s in sorted(kn.load_skills(store), key=lambda x: x.id):
        if not _is_quant_skill(s):
            continue
        measured = list(s.action.get("constraints", []))
        # stable reference for each measured constraint -- the agent cites these
        # and ingest looks them up to copy the authoritative number back in.
        refs = [kn._constraint_id(c) for c in measured]
        groups.append({
            "base_skill_id": s.id,
            "scope": dict(s.when),
            "base_confidence": s.confidence,
            "n_samples": s.evidence.get("n_samples"),
            "kernels": s.evidence.get("kernels", []),
            "measured_refs": refs,
            "measured": measured,
            "conflict_groups": list(s.action.get("conflict_groups", [])),
        })
    return {"version": 1, "redlines": REDLINES, "ask": ASK,
            "proposal_path": "ai_proposal.json", "groups": groups}


def render_brief_md(brief: Dict) -> str:
    L: List[str] = ["# Layer 2 AI articulation brief", "",
                    "Mode B (offline AI) -- you are the external agent. Read this, "
                    "write `%s`, then `tools/ingest_ai_skills.py` validates + writes "
                    "the skills." % brief["proposal_path"], "",
                    "## red lines", ""]
    for r in brief["redlines"]:
        L.append("- %s" % r)
    L += ["", "## ask", "", brief["ask"], "",
          "## proposal schema (`%s`)" % brief["proposal_path"], "",
          "```json",
          json.dumps({
              "version": 1,
              "skills": [{
                  "base_skill_id": "<one of the group ids below>",
                  "id_suffix": "pipeline",
                  "statement": "<one human-readable line>",
                  "rationale": "<why>",
                  "constraints": [
                      {"metric": "per_slot_capacity", "kind": "vmem_load",
                       "weight": 0.7, "extrapolated": False},
                      {"metric": "hint", "note": "when gap>=4, batch 2 ds_read "
                       "before the vmem_load", "weight": 0.3, "extrapolated": True},
                  ],
                  "conflict_groups": [["per_slot_capacity:vmem_load",
                                       "adjacent_cooccur:vmem_load"]],
              }],
          }, indent=2),
          "```", "",
          "- measured constraint: set `extrapolated:false` + cite it by "
          "`metric`(+`kind`, or `before`/`after` for intra_gap_order); the number "
          "is copied from Layer 1 (your `weight` is capped at the measured weight).",
          "- extrapolated rule: set `extrapolated:true` + a non-empty `note`; "
          "`weight` is capped low. Anything not measured MUST be extrapolated.",
          "", "## groups", ""]
    for g in brief["groups"]:
        L += ["### `%s`  (scope `%s`)" % (g["base_skill_id"],
                                          json.dumps(g["scope"], sort_keys=True)),
              "", "- samples: %s kernels (base_confidence=%s)"
              % (g["n_samples"], g["base_confidence"]),
              "- measured refs you may cite: %s"
              % ", ".join("`%s`" % r for r in g["measured_refs"]), ""]
        if g["conflict_groups"]:
            L.append("- Layer-1 conflict groups: %s"
                     % "; ".join(" vs ".join(grp) for grp in g["conflict_groups"]))
            L.append("")
    return "\n".join(L)


def write_brief(brief: Dict, store: str) -> Dict:
    os.makedirs(store, exist_ok=True)
    jp = os.path.join(store, "ai_brief.json")
    mp = os.path.join(store, "ai_brief.md")
    with open(jp, "w") as fh:
        json.dump(brief, fh, indent=2, sort_keys=True)
    with open(mp, "w") as fh:
        fh.write(render_brief_md(brief))
    return {"json": jp, "md": mp}


def _arg(argv, flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    store = _arg(argv, "--out", DEFAULT_OUT)
    if not os.path.isdir(kn._skills_dir(store)):
        sys.stderr.write("[brief] no skills dir under %s -- run mine_corpus first\n"
                         % store)
        return 2
    brief = build_brief(store)
    if not brief["groups"]:
        sys.stderr.write("[brief] no measured quant skills (%s) under %s\n"
                         % (QUANT_SOURCE, store))
        return 2
    paths = write_brief(brief, store)
    print("[brief] groups=%d  measured_constraints=%d"
          % (len(brief["groups"]),
             sum(len(g["measured"]) for g in brief["groups"])))
    print("[brief] json : %s" % paths["json"])
    print("[brief] md   : %s" % paths["md"])
    print("[brief] next : an AI agent writes %s, then run "
          "tools/ingest_ai_skills.py" % os.path.join(store, "ai_proposal.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
