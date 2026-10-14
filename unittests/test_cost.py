"""M9 Phase 2a: the GPU-less region cost model (reorder/cost.py).

The cost is a relative proxy for comparing orderings of the same region. We
assert it (a) distinguishes a batched single wait from N separate waits, and
(b) does not crash on degenerate (single-instruction / no-wait) regions."""
import unittest

from reorder import cost, parser, regions
from isa.gfx942.target import Gfx942Target


def _estimate(src):
    prog = parser.parse(src)
    t = Gfx942Target.from_program(prog)
    region = regions.analyze(prog, t).regions[0]
    return cost.estimate(prog, t, region)


# 3 scalar loads (lgkm) then ONE wait draining all 3.
_BATCHED = """.text
k:
  s_load_dwordx2 s[0:1], s[8:9], 0
  s_load_dwordx2 s[2:3], s[8:9], 8
  s_load_dwordx2 s[4:5], s[8:9], 16
  s_waitcnt lgkmcnt(0)
  s_endpgm
"""

# same 3 loads but each followed by its own wait (worse: no overlap).
_INTERLEAVED = """.text
k:
  s_load_dwordx2 s[0:1], s[8:9], 0
  s_waitcnt lgkmcnt(0)
  s_load_dwordx2 s[2:3], s[8:9], 8
  s_waitcnt lgkmcnt(0)
  s_load_dwordx2 s[4:5], s[8:9], 16
  s_waitcnt lgkmcnt(0)
  s_endpgm
"""

_DEGENERATE = """.text
k:
  s_endpgm
"""


class TestRegionCost(unittest.TestCase):
    def test_batched_cheaper_than_interleaved(self):
        batched = _estimate(_BATCHED)
        inter = _estimate(_INTERLEAVED)
        self.assertEqual(batched.n_waits, 1)
        self.assertEqual(inter.n_waits, 3)
        # both drain 3 outstanding loads total, but more waits = more overhead
        self.assertLess(batched.est_cycles, inter.est_cycles)

    def test_fields_sane(self):
        c = _estimate(_BATCHED)
        self.assertGreater(c.issue_cycles, 0)
        self.assertEqual(c.wait_stalls, 3)        # 3 loads drained by the one wait
        self.assertGreaterEqual(c.est_cycles, c.issue_cycles)

    def test_degenerate_region_no_crash(self):
        c = _estimate(_DEGENERATE)
        self.assertEqual(c.n_waits, 0)
        self.assertGreaterEqual(c.est_cycles, 0)

    def test_serialisable(self):
        import json
        json.loads(json.dumps(_estimate(_BATCHED).to_dict()))

    def test_estimate_lines_matches_region(self):
        """estimate_lines over the region's own lines equals estimate() (the
        sub-segment cost entry used for anchor-less fence segments)."""
        prog = parser.parse(_BATCHED)
        t = Gfx942Target.from_program(prog)
        region = regions.analyze(prog, t).regions[0]
        lines = regions.region_instr_lines(prog, region)
        whole = cost.estimate(prog, t, region)
        via_lines = cost.estimate_lines(lines, t)
        self.assertEqual(whole.to_dict(), via_lines.to_dict())

    def test_estimate_lines_subsegment(self):
        """A prefix (loads only, wait excluded) costs no wait stalls."""
        prog = parser.parse(_BATCHED)
        t = Gfx942Target.from_program(prog)
        region = regions.analyze(prog, t).regions[0]
        lines = regions.region_instr_lines(prog, region)
        loads_only = [ln for ln in lines
                      if (ln.opcode or "").startswith("s_load")]
        rc = cost.estimate_lines(loads_only, t)
        self.assertEqual(rc.n_waits, 0)
        self.assertEqual(rc.wait_stalls, 0)


if __name__ == "__main__":
    unittest.main()
