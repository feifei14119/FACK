"""Tests for the Mode A static gold-corpus skill miner (tools/mine_corpus.py).

Crucially asserts KERNEL-AGNOSTICISM: a non-GEMM kernel (kvadd_style.s, a plain
vector add with no MFMA) must mine cleanly and must NOT be classified as
mfma_dense, and no mined skill scope may embed a shape or a kernel name.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import mine_corpus as mc

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _src(name):
    with open(os.path.join(FIX, name)) as f:
        return f.read()


class TestMineKernel(unittest.TestCase):
    def test_every_region_gets_a_signature(self):
        rec = mc.mine_kernel("gemm_style", _src("gemm_style.s"))
        self.assertTrue(rec["regions"], "expected at least one region")
        for rr in rec["regions"]:
            sig = rr["signature"]
            for key in ("n_instr", "kind_hist", "anchored", "frac",
                        "waitcnt_cluster", "est_cycles"):
                self.assertIn(key, sig)
            self.assertGreater(sig["n_instr"], 0)

    def test_gemm_style_splits_into_three_regions(self):
        rec = mc.mine_kernel("gemm_style", _src("gemm_style.s"))
        kinds = {rr["kind"] for rr in rec["regions"]}
        self.assertIn("loop", kinds)
        self.assertIn("prologue", kinds)
        self.assertIn("epilogue", kinds)
        self.assertEqual(rec["kernel_class"], "mfma_dense")

    def test_per_region_specs_differ_by_region(self):
        rec = mc.mine_kernel("gemm_style", _src("gemm_style.s"))
        by_kind = {rr["kind"]: rr for rr in rec["regions"]}
        loop_ids = {mc.kn._transform_id(s) for s in by_kind["loop"]["specs"]}
        epi_ids = {mc.kn._transform_id(s) for s in by_kind["epilogue"]["specs"]}
        # the anchored loop strategy must not be identical to the drain strategy
        self.assertNotEqual(loop_ids, epi_ids)


class TestKernelAgnostic(unittest.TestCase):
    def test_non_gemm_kernel_is_not_mfma_dense(self):
        rec = mc.mine_kernel("kvadd_style", _src("kvadd_style.s"))
        # vector-add has no MFMA -> must NOT be classified as an mfma kernel
        self.assertNotIn("mfma", rec["kernel_class"])
        for rr in rec["regions"]:
            self.assertFalse(rr["signature"]["anchored"])
            self.assertGreater(rr["signature"]["n_instr"], 0)

    def test_sidecar_meta_overrides_class_and_arch(self):
        rec = mc.mine_kernel("k", _src("kvadd_style.s"),
                             meta={"arch": "gfx950", "kernel_class": "elementwise"})
        self.assertEqual(rec["arch"], "gfx950")
        self.assertEqual(rec["kernel_class"], "elementwise")


class TestBuildSkills(unittest.TestCase):
    def setUp(self):
        self.records = [mc.mine_kernel(n, _src(n + ".s"))
                        for n in ("gemm_style", "kvadd_style", "coldstart_mfma")]
        self.skills = mc.build_skills(self.records)

    def test_all_candidate_status(self):
        self.assertTrue(self.skills)
        for s in self.skills:
            self.assertEqual(s.status, "candidate",
                             "Mode A must never auto-promote to trusted")

    def test_scope_has_no_shape_or_kernel_name(self):
        kernel_names = {r["name"] for r in self.records}
        for s in self.skills:
            self.assertEqual(set(s.when) - {"arch", "loop_kind", "region"}, set(),
                             "skill scope may only use structural keys")
            for v in s.when.values():
                self.assertNotIn(v, kernel_names)
            # no shape-ish tokens leaked into the scope
            blob = json.dumps(s.when)
            for tok in ("m=", "n=", "k=", "qhead", "ctx_len"):
                self.assertNotIn(tok, blob)

    def test_skill_id_is_region_scoped(self):
        ids = {s.id for s in self.skills}
        self.assertIn("gold-mfma_dense-loop", ids)


class TestQuantProfile(unittest.TestCase):
    """Fine-grained, MEASURED MFMA-gap layout profile (Layer 1)."""

    def test_anchored_loop_has_quant_anchorless_does_not(self):
        rec = mc.mine_kernel("gemm_style", _src("gemm_style.s"))
        by_kind = {rr["kind"]: rr for rr in rec["regions"]}
        loop_q = by_kind["loop"]["signature"]["quant"]
        self.assertIsNotNone(loop_q, "anchored loop must yield a quant profile")
        gap = loop_q["mfma_gap_size"]["stats"]
        for key in ("min", "median", "max", "n"):
            self.assertIn(key, gap)
        self.assertGreaterEqual(loop_q["n_slots"], 1)
        # an anchor-less region (no MFMA) must NOT fabricate a gap profile
        self.assertIsNone(by_kind["prologue"]["signature"]["quant"])

    def test_intra_gap_order_only_uses_schedulable_fillers(self):
        # fences/anchors (branch/barrier/waitcnt/set_m0) must NOT appear in the
        # intra-gap ordering -- only schedulable fillers (_QUANT_KINDS).
        for name in ("gemm_style", "coldstart_mfma"):
            rec = mc.mine_kernel(name, _src(name + ".s"))
            for rr in rec["regions"]:
                q = rr["signature"].get("quant")
                if not q:
                    continue
                for o in q["intra_gap_order"]:
                    self.assertIn(o["before"], mc._QUANT_KIND_VALUES)
                    self.assertIn(o["after"], mc._QUANT_KIND_VALUES)

    def test_quant_numbers_come_from_the_gold_order(self):
        # the measured ranges must reflect the actual instruction stream, never
        # a hard-coded constant: gap size cannot exceed the region length.
        rec = mc.mine_kernel("coldstart_mfma", _src("coldstart_mfma.s"))
        for rr in rec["regions"]:
            q = rr["signature"].get("quant")
            if not q:
                continue
            n = rr["signature"]["n_instr"]
            self.assertLessEqual(q["mfma_gap_size"]["stats"]["max"], n)

    def _synthetic_record(self):
        """A crafted gold profile: each MFMA slot can hold up to 4 ds_read, but
        neighbouring slots are NEVER both filled (skillA vs skillB tension)."""
        quant = {
            "n_slots": 4,
            "mfma_gap_size": {"raw": [5, 5, 5, 5], "stats": mc._stats([5, 5, 5, 5])},
            "per_slot_capacity": {
                "ds_read": {"raw": [4, 0, 4, 0], "stats": mc._stats([4, 0, 4, 0])}},
            "burst_runlen": {"ds_read": {"raw": [4, 4], "stats": mc._stats([4, 4])}},
            "intra_gap_order": [
                {"before": "ds_read", "after": "vmem_load", "n": 4, "freq": 1.0}],
            "adjacent_cooccur": {
                "ds_read": {"rate": 0.0, "both": 0, "either": 4, "n_pairs": 3}},
        }
        return {"name": "synthA", "arch": "gfx942", "kernel_class": "mfma_dense",
                "regions": [{"kind": "loop", "signature": {"quant": quant}}]}

    def test_quant_skill_carries_weighted_constraints_no_leak(self):
        skills = mc.build_quant_skills([self._synthetic_record()])
        self.assertEqual(len(skills), 1)
        s = skills[0]
        self.assertEqual(s.status, "candidate")
        self.assertEqual(set(s.when), {"arch", "loop_kind", "region"})
        self.assertNotIn("synthA", json.dumps(s.when))
        cons = s.action["constraints"]
        self.assertTrue(cons)
        metrics = {c["metric"] for c in cons}
        self.assertEqual(metrics,
                         {"mfma_gap_size", "per_slot_capacity",
                          "burst_runlen", "adjacent_cooccur", "intra_gap_order"})
        for c in cons:
            self.assertGreater(c["weight"], 0.0)
            self.assertLessEqual(c["weight"], 0.9)

    def test_conflict_group_when_capacity_high_but_adjacency_low(self):
        skills = mc.build_quant_skills([self._synthetic_record()])
        groups = skills[0].action.get("conflict_groups")
        self.assertEqual(groups, [["per_slot_capacity:ds_read",
                                   "adjacent_cooccur:ds_read"]])

    def test_no_conflict_group_when_adjacency_high(self):
        rec = self._synthetic_record()
        rec["regions"][0]["signature"]["quant"]["adjacent_cooccur"]["ds_read"] = {
            "rate": 0.9, "both": 3, "either": 4, "n_pairs": 3}
        skills = mc.build_quant_skills([rec])
        self.assertNotIn("conflict_groups", skills[0].action)


class TestInstructionSubTyping(unittest.TestCase):
    """MFMA shape + LDS/VMEM width sub-typing (the "one mfma / one lds" fix)."""

    def test_mfma_class_parses_shape_token(self):
        self.assertEqual(mc.mfma_class("v_mfma_f32_16x16x16_bf16"), "16x16x16")
        self.assertEqual(mc.mfma_class("v_mfma_f32_32x32x8_bf16"), "32x32x8")
        self.assertEqual(mc.mfma_class("v_smfmac_f32_16x16x32_f16"), "16x16x32")
        # no shape -> safe fallback, never dropped
        self.assertEqual(mc.mfma_class("v_mfma_weird"), "mfma")
        self.assertEqual(mc.mfma_class(None), "mfma")

    def test_access_width_bits_and_subkind(self):
        self.assertEqual(mc.access_width_bits("ds_read_b128"), 128)
        self.assertEqual(mc.access_width_bits("ds_read_b64"), 64)
        self.assertEqual(mc.access_width_bits("global_load_b32"), 32)
        self.assertEqual(mc.access_width_bits("buffer_load_dword"), 32)
        self.assertEqual(mc.access_width_bits("buffer_load_dwordx4"), 128)
        # the MFMA mnemonic must NOT be mistaken for a 16-bit access via "bf16"
        self.assertIsNone(mc.access_width_bits("v_mfma_f32_16x16x16_bf16"))
        self.assertEqual(mc.filler_subkind("ds_read_b128"), "128b")
        self.assertIsNone(mc.filler_subkind("v_add_f32"))

    def _anchored_quant(self, name):
        rec = mc.mine_kernel(name, _src(name + ".s"))
        for rr in rec["regions"]:
            q = rr["signature"].get("quant")
            if q:
                return q
        self.fail("expected an anchored region with a quant profile")

    def test_by_mfma_class_separates_shapes(self):
        q = self._anchored_quant("multimfma_style")
        by_cls = q["by_mfma_class"]
        self.assertEqual(set(by_cls), {"16x16x16", "32x32x8"})
        # the 32x32x8 gap (higher latency) must measure LARGER than the 16x16x16
        # gap -- the exact distinction the old single-bucket model erased.
        g_small = by_cls["16x16x16"]["mfma_gap_size"]["stats"]["median"]
        g_big = by_cls["32x32x8"]["mfma_gap_size"]["stats"]["median"]
        self.assertGreater(g_big, g_small)

    def test_per_slot_capacity_breaks_down_by_width(self):
        q = self._anchored_quant("multimfma_style")
        # the 32x32x8 gap is filled with b128 ds_reads; the 16x16x16 gap with b64.
        big = q["by_mfma_class"]["32x32x8"]["per_slot_capacity"]["ds_read"]
        self.assertIn("by_width", big)
        self.assertIn("128b", big["by_width"])
        small = q["by_mfma_class"]["16x16x16"]["per_slot_capacity"]["ds_read"]
        self.assertIn("64b", small.get("by_width", {}))

    def test_top_level_fields_stay_back_compatible(self):
        # downstream (brief/ingest/planner) still reads the pooled top-level keys.
        q = self._anchored_quant("multimfma_style")
        for key in ("n_slots", "mfma_gap_size", "per_slot_capacity",
                    "burst_runlen", "intra_gap_order", "adjacent_cooccur"):
            self.assertIn(key, q)
        self.assertEqual(sum(q["mfma_class_hist"].values()), q["n_slots"])


class TestQuantSkillMfmaClass(unittest.TestCase):
    """build_quant_skills must surface the per-shape + per-width refinements as
    referenceable constraints (so brief/ingest/planner can consume them)."""

    def _skill(self):
        rec = mc.mine_kernel("multimfma_style", _src("multimfma_style.s"))
        skills = mc.build_quant_skills([rec])
        quant = [s for s in skills if "constraints" in s.action]
        self.assertTrue(quant, "expected a quant constraint skill")
        return quant[0]

    def test_per_class_and_width_constraints_emitted(self):
        cons = self._skill().action["constraints"]
        classes = {c.get("mfma_class") for c in cons if c.get("mfma_class")}
        self.assertEqual(classes, {"16x16x16", "32x32x8"})
        # a bigger-shape gap must record a larger measured capacity than a smaller.
        def cap(cls):
            for c in cons:
                if (c.get("metric") == "per_slot_capacity" and c.get("kind") == "ds_read"
                        and c.get("mfma_class") == cls and not c.get("width")):
                    return c["stat"]["median"]
            return None
        self.assertGreater(cap("32x32x8"), cap("16x16x16"))
        # width breakdown present (the b64 vs b128 signal)
        widths = {c.get("width") for c in cons if c.get("width")}
        self.assertTrue({"64b", "128b"} & widths)

    def test_pooled_constraints_still_present_and_refs_unique(self):
        cons = self._skill().action["constraints"]
        # the historical pooled constraints (no mfma_class) still exist ...
        self.assertTrue(any(c.get("metric") == "mfma_gap_size"
                            and not c.get("mfma_class") for c in cons))
        # ... and every constraint gets a UNIQUE reference id (brief<->proposal).
        ids = [mc.kn._constraint_id(c) for c in cons]
        self.assertEqual(len(ids), len(set(ids)), "constraint refs must be unique")

    def _two_class_record(self):
        """Two MFMA shapes; the 16x16x16 gaps pack many ds_read but never in
        adjacent gaps (a per-shape conflict), the 32x32x8 gaps do not."""
        def _cap(raw):
            return {"raw": raw, "stats": mc._stats(raw),
                    "by_width": {"128b": {"raw": raw, "stats": mc._stats(raw)}}}
        by_cls = {
            "16x16x16": {
                "mfma_gap_size": {"raw": [5, 5, 5, 5], "stats": mc._stats([5] * 4)},
                "per_slot_capacity": {"ds_read": _cap([4, 0, 4, 0])},
                "adjacent_cooccur": {"ds_read": {"both": 0, "either": 4, "n_pairs": 3}},
                "intra_gap_order": []},
            "32x32x8": {
                "mfma_gap_size": {"raw": [8, 8], "stats": mc._stats([8, 8])},
                "per_slot_capacity": {"ds_read": _cap([6, 6])},
                "adjacent_cooccur": {"ds_read": {"both": 2, "either": 2, "n_pairs": 1}},
                "intra_gap_order": []},
        }
        quant = {
            "n_slots": 6,
            "mfma_gap_size": {"raw": [5, 5, 5, 5, 8, 8], "stats": mc._stats([5, 5, 5, 5, 8, 8])},
            "per_slot_capacity": {"ds_read": {"raw": [4, 0, 4, 0, 6, 6],
                                              "stats": mc._stats([4, 0, 4, 0, 6, 6])}},
            "burst_runlen": {}, "intra_gap_order": [], "adjacent_cooccur": {},
            "by_mfma_class": by_cls,
            "mfma_class_hist": {"16x16x16": 4, "32x32x8": 2},
        }
        return {"name": "twocls", "arch": "gfx942", "kernel_class": "mfma_dense",
                "regions": [{"kind": "loop", "signature": {"quant": quant}}]}

    def test_per_shape_conflict_group(self):
        skills = mc.build_quant_skills([self._two_class_record()])
        groups = skills[0].action.get("conflict_groups", [])
        self.assertIn(["per_slot_capacity@16x16x16:ds_read",
                       "adjacent_cooccur@16x16x16:ds_read"], groups)
        # the 32x32x8 shape co-occurs freely -> no conflict group for it.
        self.assertFalse(any("32x32x8" in m for g in groups for m in g))


class TestCorpusIngestAndOutputs(unittest.TestCase):
    def test_iter_corpus_reads_dirs_bares_and_meta(self):
        with tempfile.TemporaryDirectory() as d:
            # (a) subdir kernel with sidecar meta
            k1 = os.path.join(d, "k1")
            os.makedirs(k1)
            with open(os.path.join(k1, "kernel.s"), "w") as f:
                f.write(_src("gemm_style.s"))
            with open(os.path.join(k1, "meta.json"), "w") as f:
                json.dump({"arch": "gfx942", "kernel_class": "myfamily"}, f)
            # (b) bare .s file
            with open(os.path.join(d, "k2.s"), "w") as f:
                f.write(_src("kvadd_style.s"))

            records = mc.mine_corpus(d)
            by_name = {r["name"]: r for r in records}
            self.assertIn("k1", by_name)
            self.assertIn("k2", by_name)
            self.assertEqual(by_name["k1"]["kernel_class"], "myfamily")

    def test_write_outputs_lands_under_out_store_only(self):
        records = [mc.mine_kernel("gemm_style", _src("gemm_style.s"))]
        skills = mc.build_skills(records)
        with tempfile.TemporaryDirectory() as out:
            paths = mc.write_outputs(records, skills, out)
            self.assertTrue(os.path.isfile(paths["report"]))
            self.assertTrue(os.path.isdir(paths["skills_dir"]))
            saved = [f for f in os.listdir(paths["skills_dir"]) if f.endswith(".json")]
            self.assertTrue(saved)
            # each saved skill round-trips and is a candidate
            with open(os.path.join(paths["skills_dir"], saved[0])) as f:
                obj = json.load(f)
            self.assertEqual(obj["status"], "candidate")


if __name__ == "__main__":
    unittest.main()
