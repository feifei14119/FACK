"""M1 tests: read-only waitcnt parsing + counter simulation."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, waitcnt

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return parser.parse(f.read())


class TestWaitcntFixture(unittest.TestCase):
    def setUp(self):
        self.prog = _load(os.path.join(FIX, "gemm_style.s"))
        self.t = Gfx942Target.from_program(self.prog)

    def test_parse_existing(self):
        events = waitcnt.parse_existing(self.prog, self.t)
        # gemm fixture has several waits incl 'vmcnt(20) lgkmcnt(0)' and a full one
        self.assertTrue(events)
        full = [e for e in events
                if e.targets.get("vm") == 0 and e.targets.get("lgkm") == 0
                and e.targets.get("exp") == 0]
        self.assertTrue(full)  # the final s_waitcnt vmcnt(0) expcnt(0) lgkmcnt(0)

    def test_simulate_runs(self):
        res = waitcnt.simulate(self.prog, self.t)
        self.assertTrue(res.events)
        # after the final full wait, all counters should be drained
        self.assertEqual(res.final_outstanding["vm"], 0)
        self.assertEqual(res.final_outstanding["lgkm"], 0)


class TestWaitcntVscnt(unittest.TestCase):
    def test_vscnt_sim(self):
        text = (".text\n"
                "k:\n"
                "  global_store_b32 v[2:3], v4, off\n"
                "  global_store_b32 v[2:3], v5, off\n"
                "  s_waitcnt_vscnt null, 0\n"
                "  s_endpgm\n")
        prog = parser.parse(text)
        t = Gfx942Target()
        res = waitcnt.simulate(prog, t)
        self.assertEqual(res.final_outstanding["vs"], 0)
        # the vscnt wait event drained from 2 -> 0
        ev = [e for e in res.events if e.opcode == "s_waitcnt_vscnt"][0]
        self.assertEqual(ev.before["vs"], 2)
        self.assertEqual(ev.after["vs"], 0)


class TestScalarLoadLgkm(unittest.TestCase):
    """Scalar loads (SMEM) share the lgkm counter with LDS but complete OUT OF
    ORDER, so a staged lgkmcnt(N>0) can never prove a specific scalar load is
    back -- the recompute must force lgkmcnt(0) before the consumer."""

    def _waits(self, text):
        prog = parser.parse(text)
        t = Gfx942Target()
        return prog, t, waitcnt.compute_waits(prog.instr_lines(), t)

    def test_two_scalar_loads_force_full_drain(self):
        # 2 outstanding s_loads; consumer of the FIRST must wait lgkmcnt(0),
        # NOT lgkmcnt(1) (which would only guarantee an *in-order* producer).
        text = (".text\n"
                "k:\n"
                "  s_load_dword s0, s[8:9], 0x0\n"
                "  s_load_dword s1, s[8:9], 0x4\n"
                "  s_add_u32 s2, s0, 1\n"
                "  s_endpgm\n")
        prog, t, need = self._waits(text)
        add = [ln for ln in prog.instr_lines() if ln.opcode == "s_add_u32"][0]
        self.assertIn(add.idx, need)
        self.assertEqual(need[add.idx].get("lgkm"), 0)

    def test_scalar_load_not_staged_like_lds(self):
        # consumer of the SECOND load also drains to 0 (out-of-order return).
        text = (".text\n"
                "k:\n"
                "  s_load_dword s0, s[8:9], 0x0\n"
                "  s_load_dword s1, s[8:9], 0x4\n"
                "  s_add_u32 s2, s1, 1\n"
                "  s_endpgm\n")
        prog, t, need = self._waits(text)
        add = [ln for ln in prog.instr_lines() if ln.opcode == "s_add_u32"][0]
        self.assertEqual(need[add.idx].get("lgkm"), 0)

    def test_pure_lds_still_staged(self):
        # regression: LDS reads return IN ORDER -> staged lgkmcnt(N) preserved.
        text = (".text\n"
                "k:\n"
                "  ds_read_b32 v0, v10\n"
                "  ds_read_b32 v1, v10 offset:4\n"
                "  v_add_f32 v2, v0, v0\n"
                "  s_endpgm\n")
        prog, t, need = self._waits(text)
        add = [ln for ln in prog.instr_lines() if ln.opcode == "v_add_f32"][0]
        # first ds_read consumer: 1 later lds op still outstanding -> lgkmcnt(1)
        self.assertEqual(need[add.idx].get("lgkm"), 1)


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestWaitcntRealShader(unittest.TestCase):
    def test_reads_all_forms(self):
        prog = _load(SHADER)
        t = Gfx942Target.from_program(prog)
        events = waitcnt.parse_existing(prog, t)
        self.assertTrue(events)
        # real shader uses numeric '0x0000', 'vmcnt(N) & lgkmcnt(0)', 'lgkmcnt(0)'
        forms = {tuple(sorted(k for k, v in e.targets.items() if v is not None))
                 for e in events}
        self.assertTrue(any("vm" in f and "lgkm" in f for f in forms))


if __name__ == "__main__":
    unittest.main()
