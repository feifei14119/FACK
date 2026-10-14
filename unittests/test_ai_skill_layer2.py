"""Tests for Layer 2 (offline AI articulation): ai_skill_brief (export) +
ingest_ai_skills (validate/ingest).

The gate is the whole point: an AI agent may articulate + extrapolate, but it
must be IMPOSSIBLE to (a) invent a "measured" number, (b) widen scope, or
(c) auto-promote past candidate. Every test pins one of those guarantees.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import knowledge as kn
from agent.knowledge import Skill
from tools import ai_skill_brief as brief_mod
from tools import ingest_ai_skills as ing


def _quant_skill():
    return Skill(
        id="gold-mfma_dense-loop-quant",
        statement="[gold-mined, static-quant] mfma_dense/loop",
        when={"arch": "gfx942", "loop_kind": "mfma_dense", "region": "loop"},
        action={"constraints": [
            {"metric": "mfma_gap_size",
             "stat": {"median": 2.0, "max": 20.0, "min": 0.0, "n": 10}, "weight": 0.9},
            {"metric": "per_slot_capacity", "kind": "vmem_load",
             "stat": {"median": 1.0, "max": 5.0, "min": 0.0, "n": 10}, "weight": 0.9},
            {"metric": "intra_gap_order", "before": "ds_read", "after": "salu",
             "freq": 1.0, "weight": 0.9},
        ]},
        evidence={"kernels": ["k1", "k2"], "n_samples": 2,
                  "source": brief_mod.QUANT_SOURCE},
        effect={"note": "measured"},
        confidence=0.886,
        status="candidate",
    )


def _store_with_quant():
    d = tempfile.mkdtemp()
    kn.save_skill(_quant_skill(), d)
    # a non-quant gold skill must be ignored by the brief
    kn.save_skill(Skill(id="gold-mfma_dense-loop", statement="x",
                        when={"arch": "gfx942"}, action={"specs": [{"kind": "listsched"}]},
                        evidence={"source": "gold_corpus(modeA)"}), d)
    return d


class TestBrief(unittest.TestCase):
    def test_brief_picks_only_quant_skills_with_refs(self):
        d = _store_with_quant()
        b = brief_mod.build_brief(d)
        self.assertEqual(len(b["groups"]), 1)
        g = b["groups"][0]
        self.assertEqual(g["base_skill_id"], "gold-mfma_dense-loop-quant")
        self.assertIn("mfma_gap_size", g["measured_refs"])
        self.assertIn("per_slot_capacity:vmem_load", g["measured_refs"])
        self.assertIn("intra_gap_order:ds_read>salu", g["measured_refs"])
        self.assertTrue(b["redlines"] and b["ask"])

    def test_brief_md_renders(self):
        d = _store_with_quant()
        md = brief_mod.render_brief_md(brief_mod.build_brief(d))
        self.assertIn("red lines", md)
        self.assertIn("gold-mfma_dense-loop-quant", md)


def _brief():
    return brief_mod.build_brief(_store_with_quant())


class TestIngestGate(unittest.TestCase):
    def test_measured_constraint_copies_authoritative_number(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [
                {"metric": "per_slot_capacity", "kind": "vmem_load",
                 "stat": {"median": 99.0, "max": 99.0}, "weight": 0.8,
                 "extrapolated": False}],
        }]}
        skills, warns = ing.validate_proposal(prop, _brief())
        self.assertEqual(len(skills), 1)
        c = skills[0].action["constraints"][0]
        self.assertEqual(c["stat"]["median"], 1.0)   # authoritative, not 99
        self.assertEqual(c["stat"]["max"], 5.0)
        self.assertLessEqual(c["weight"], 0.9)
        self.assertTrue(any("authoritative" in w for w in warns))

    def test_hallucinated_measured_ref_dropped(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [
                {"metric": "per_slot_capacity", "kind": "made_up",
                 "weight": 0.9, "extrapolated": False}],
        }]}
        skills, warns = ing.validate_proposal(prop, _brief())
        self.assertEqual(skills, [])
        self.assertTrue(any("no such Layer-1 ref" in w for w in warns))

    def test_extrapolated_needs_note_and_is_capped(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [
                {"metric": "mfma_gap_size", "extrapolated": False},  # anchor it valid
                {"metric": "hint", "weight": 0.95, "extrapolated": True},  # no note -> drop
                {"metric": "hint", "note": "batch 2 ds_read when gap>=4",
                 "weight": 0.95, "extrapolated": True}],
        }]}
        skills, warns = ing.validate_proposal(prop, _brief())
        self.assertEqual(len(skills), 1)
        cs = skills[0].action["constraints"]
        ext = [c for c in cs if c.get("extrapolated")]
        self.assertEqual(len(ext), 1)
        self.assertLessEqual(ext[0]["weight"], ing.EXTRAP_CAP)
        self.assertEqual(ext[0]["source"], "ai-hypothesis")
        self.assertLessEqual(skills[0].confidence, ing.EXTRAP_CAP)
        self.assertTrue(any("without a note" in w for w in warns))

    def test_measured_only_skill_capped_below_gold(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [{"metric": "mfma_gap_size", "extrapolated": False}],
        }]}
        skills, _ = ing.validate_proposal(prop, _brief())
        self.assertEqual(len(skills), 1)
        self.assertLessEqual(skills[0].confidence, ing.MEASURED_AI_CAP)
        self.assertLess(skills[0].confidence, 0.886)

    def test_unknown_base_dropped(self):
        prop = {"skills": [{"base_skill_id": "nope", "id_suffix": "p",
                            "constraints": [{"metric": "mfma_gap_size",
                                             "extrapolated": False}]}]}
        skills, warns = ing.validate_proposal(prop, _brief())
        self.assertEqual(skills, [])
        self.assertTrue(any("unknown base_skill_id" in w for w in warns))

    def test_scope_is_structural_only_and_status_candidate(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [{"metric": "mfma_gap_size", "extrapolated": False}],
        }]}
        skills, _ = ing.validate_proposal(prop, _brief())
        s = skills[0]
        self.assertEqual(set(s.when), {"arch", "loop_kind", "region"})
        self.assertEqual(s.status, "candidate")
        self.assertEqual(s.evidence["source"], ing.AI_SOURCE)
        self.assertEqual(s.evidence["based_on"], "gold-mfma_dense-loop-quant")

    def test_conflict_group_with_unresolved_member_dropped(self):
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "p",
            "constraints": [{"metric": "per_slot_capacity", "kind": "vmem_load",
                             "extrapolated": False}],
            "conflict_groups": [["per_slot_capacity:vmem_load", "ghost:x"]],
        }]}
        skills, warns = ing.validate_proposal(prop, _brief())
        self.assertNotIn("conflict_groups", skills[0].action)
        self.assertTrue(any("unresolved members" in w for w in warns))


class TestIntegrationWithSeedPlan(unittest.TestCase):
    def test_ai_skill_does_not_override_measured_constraint(self):
        d = _store_with_quant()
        # AI restates the measured vmem_load capacity (lower confidence) + adds a
        # genuine extrapolation. seed_search_plan must keep the MEASURED number.
        prop = {"skills": [{
            "base_skill_id": "gold-mfma_dense-loop-quant", "id_suffix": "pipe",
            "constraints": [
                {"metric": "per_slot_capacity", "kind": "vmem_load",
                 "weight": 0.5, "extrapolated": False},
                {"metric": "hint", "kind": "vmem_load",
                 "note": "front-load when gap>=4", "weight": 0.3,
                 "extrapolated": True}],
        }]}
        skills, _ = ing.validate_proposal(prop, brief_mod.build_brief(d))
        for s in skills:
            kn.save_skill(s, d)
        plan = kn.seed_search_plan(
            {"arch": "gfx942", "loop_kind": "mfma_dense", "region": "loop"}, store=d)
        cap = [c for c in plan["constraints"]
               if c.get("metric") == "per_slot_capacity"
               and c.get("kind") == "vmem_load"]
        self.assertEqual(len(cap), 1)
        self.assertEqual(cap[0]["weight"], 0.9)        # gold's, not the AI 0.5
        self.assertIn("ai-mfma_dense-loop-pipe", plan["skills_used"])
        # the extrapolated hint is genuinely NEW, so it must survive the merge.
        self.assertTrue(any(c.get("extrapolated") for c in plan["constraints"]))


if __name__ == "__main__":
    unittest.main()
