"""Tests for the Layer 3 constraint consumer (agent/layout_planner.py): turning
gold-mined QUANT constraints + conflict_groups into ranked candidate gap layouts.
Pure data in / out -- no GPU, no editor, no parsed kernel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import layout_planner as lp


def _constraints():
    return [
        {"metric": "mfma_gap_size", "stat": {"median": 2, "max": 6}, "weight": 0.9},
        {"metric": "per_slot_capacity", "kind": "vmem_load",
         "stat": {"median": 1, "max": 2}, "weight": 0.9},
        {"metric": "per_slot_capacity", "kind": "ds_read",
         "stat": {"median": 2, "max": 2}, "weight": 0.8},
        {"metric": "adjacent_cooccur", "kind": "vmem_load",
         "value": 0.9, "polarity": "ok", "weight": 0.87},
        {"metric": "adjacent_cooccur", "kind": "ds_read",
         "value": 0.0, "polarity": "avoid", "weight": 0.8},
        {"metric": "intra_gap_order", "before": "salu", "after": "vmem_load",
         "freq": 1.0, "weight": 0.9},
        {"metric": "intra_gap_order", "before": "salu", "after": "ds_read",
         "freq": 1.0, "weight": 0.9},
        {"metric": "intra_gap_order", "before": "vmem_load", "after": "ds_read",
         "freq": 1.0, "weight": 0.9},
    ]


CONFLICT = [["per_slot_capacity:ds_read", "adjacent_cooccur:ds_read"]]


class TestPrimitives(unittest.TestCase):
    def test_slot_priority_strided_first(self):
        self.assertEqual(lp._slot_priority(4, 1), [0, 1, 2, 3])
        self.assertEqual(lp._slot_priority(4, 2), [0, 2, 1, 3])

    def test_distribute_spread_uses_non_adjacent_slots_first(self):
        # 2 ds_read, cap 1, stride 2 over 4 slots -> slots {0,2} (no neighbours)
        layout = lp._distribute([10, 11], 4, cap=1, stride=2)
        self.assertEqual(set(layout), {0, 2})

    def test_distribute_pack_groups_by_capacity(self):
        layout = lp._distribute([10, 11, 12, 13], 4, cap=2, stride=1)
        self.assertEqual(layout[0], [10, 11])
        self.assertEqual(layout[1], [12, 13])


class TestPlanner(unittest.TestCase):
    def test_empty_when_no_slots_or_no_fillers(self):
        f = [{"iid": 1, "kind": "vmem_load", "movable": True}]
        self.assertEqual(lp.plan_candidate_layouts(0, f, _constraints()), [])
        self.assertEqual(lp.plan_candidate_layouts(4, [], _constraints()), [])

    def test_immovable_fillers_ignored(self):
        f = [{"iid": 1, "kind": "vmem_load", "movable": False}]
        self.assertEqual(lp.plan_candidate_layouts(4, f, _constraints()), [])

    def test_vmem_spreads_one_per_slot(self):
        f = [{"iid": i, "kind": "vmem_load", "movable": True} for i in range(4)]
        plans = lp.plan_candidate_layouts(4, f, _constraints())
        self.assertTrue(plans)
        layout = plans[0]["layout"]
        # cooccur=ok + capacity median 1 => exactly one vmem per slot
        self.assertEqual(sorted(layout), [0, 1, 2, 3])
        for slot, iids in layout.items():
            self.assertEqual(len(iids), 1)

    def test_conflict_yields_pack_and_spread_variants(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(2)]
        plans = lp.plan_candidate_layouts(4, f, _constraints(), CONFLICT)
        self.assertGreaterEqual(len(plans), 2, "conflict must expand to variants")
        max_per_slot = [max((iids and len(iids)) for iids in p["layout"].values())
                        for p in plans]
        n_slots_used = [len(p["layout"]) for p in plans]
        # one variant PACKS both ds into a single slot (capacity satisfied)...
        self.assertIn(2, max_per_slot)
        # ...another SPREADS them across two distinct slots (adjacency satisfied).
        self.assertIn(2, n_slots_used)

    def test_intra_gap_order_within_slot(self):
        # one of each kind, single slot -> measured precedence salu<vmem<ds.
        # iids deliberately out of precedence order to prove rank (not iid) wins.
        f = [{"iid": 20, "kind": "ds_read", "movable": True},
             {"iid": 10, "kind": "vmem_load", "movable": True},
             {"iid": 30, "kind": "salu", "movable": True}]
        plans = lp.plan_candidate_layouts(1, f, _constraints())
        self.assertEqual(plans[0]["layout"][0], [30, 10, 20])  # salu, vmem, ds

    def test_candidates_sorted_by_score_desc(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(2)]
        plans = lp.plan_candidate_layouts(4, f, _constraints(), CONFLICT)
        scores = [p["score"] for p in plans]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(scores[0], 0.0)

    def test_respects_max_candidates(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(4)]
        plans = lp.plan_candidate_layouts(6, f, _constraints(), CONFLICT,
                                          max_candidates=1)
        self.assertEqual(len(plans), 1)


class TestMfmaClassAware(unittest.TestCase):
    """Per-gap capacity keyed on the MFMA shape that opens each gap."""

    def _class_constraints(self):
        return [
            # pooled fallback (used when a gap's shape has no specific rule)
            {"metric": "per_slot_capacity", "kind": "ds_read",
             "stat": {"median": 1, "max": 1}, "weight": 0.8},
            {"metric": "per_slot_capacity", "kind": "ds_read",
             "mfma_class": "16x16x16", "stat": {"median": 1, "max": 1}, "weight": 0.8},
            {"metric": "per_slot_capacity", "kind": "ds_read",
             "mfma_class": "32x32x8", "stat": {"median": 4, "max": 4}, "weight": 0.8},
            # a width sub-constraint must NOT be mistaken for a kind-level capacity
            {"metric": "per_slot_capacity", "kind": "ds_read",
             "mfma_class": "32x32x8", "width": "128b",
             "stat": {"median": 4, "max": 4}, "weight": 0.8},
        ]

    def test_capacity_prefers_class_then_falls_back(self):
        cs = self._class_constraints()
        self.assertEqual(lp._capacity(cs, "ds_read", "32x32x8")["stat"]["median"], 4)
        self.assertEqual(lp._capacity(cs, "ds_read", "16x16x16")["stat"]["median"], 1)
        # unknown shape -> pooled fallback
        self.assertEqual(lp._capacity(cs, "ds_read", "64x64x1")["stat"]["median"], 1)
        # width sub-constraint is never returned as the kind-level capacity
        self.assertIsNone(lp._capacity(cs, "ds_read", "32x32x8").get("width"))

    def test_bigger_shape_gap_packs_more_fillers(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(5)]
        # gap0 opened by 16x16x16 (cap 1), gap1 by 32x32x8 (cap 4)
        plans = lp.plan_candidate_layouts(
            2, f, self._class_constraints(), gap_classes=["16x16x16", "32x32x8"])
        self.assertTrue(plans)
        layout = plans[0]["layout"]
        self.assertEqual(len(layout[0]), 1, "16x16x16 gap holds its measured 1")
        self.assertEqual(len(layout[1]), 4, "32x32x8 gap holds its measured 4")

    def test_without_gap_classes_treats_gaps_equally(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(4)]
        plans = lp.plan_candidate_layouts(2, f, self._class_constraints())
        # pooled sizing spreads the fillers EVENLY (no shape asymmetry): 2 vs 2,
        # never the 1-vs-4 split the class-aware path produces.
        layout = plans[0]["layout"]
        self.assertEqual(len(layout[0]), len(layout[1]))

    def test_ignored_when_length_mismatch(self):
        f = [{"iid": i, "kind": "ds_read", "movable": True} for i in range(3)]
        pooled = lp.plan_candidate_layouts(2, f, self._class_constraints())
        # wrong-length gap_classes must be ignored -> identical to pooled sizing.
        mismatched = lp.plan_candidate_layouts(
            2, f, self._class_constraints(), gap_classes=["32x32x8"])
        self.assertEqual([p["layout"] for p in mismatched],
                         [p["layout"] for p in pooled])


if __name__ == "__main__":
    unittest.main()
