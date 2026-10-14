"""M2 tests: dependency graph + legal windows, on synthetic programs,
fixtures, AND the real testcase/ kernel."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.depgraph import DepGraph
from reorder.model import EdgeType

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _graph(text):
    prog = parser.parse(text)
    t = Gfx942Target.from_program(prog)
    lines = [ln for ln in prog.lines if ln.kind.value == "instr"]
    return prog, t, DepGraph.build(lines, t)


def _find(g, opcode, nth=0):
    """Return the iid of the nth instruction whose opcode startswith opcode."""
    hits = [n.iid for n in g.nodes if (n.line.opcode or "").startswith(opcode)]
    return hits[nth]


def _has_edge(g, a, b, etype=None):
    for (s, d, t) in g.edges():
        if s == a and d == b and (etype is None or t is etype):
            return True
    return False


class TestRegisterHazards(unittest.TestCase):
    def test_raw(self):
        _, _, g = _graph(".text\nk:\n  v_add_f32 v4, v2, v3\n"
                         "  v_mul_f32 v5, v4, v2\n  s_endpgm\n")
        a, b = _find(g, "v_add"), _find(g, "v_mul")
        self.assertTrue(_has_edge(g, a, b, EdgeType.RAW))

    def test_waw_and_war(self):
        _, _, g = _graph(".text\nk:\n  v_add_f32 v4, v2, v3\n"
                         "  v_mul_f32 v6, v4, v2\n  v_mov_b32 v4, 0\n  s_endpgm\n")
        add, mul, mov = _find(g, "v_add"), _find(g, "v_mul"), _find(g, "v_mov")
        self.assertTrue(_has_edge(g, add, mov, EdgeType.WAW))   # both write v4
        self.assertTrue(_has_edge(g, mul, mov, EdgeType.WAR))   # mul reads v4 before mov

    def test_compare_operand0_is_source_not_dest(self):
        # s_cmp reads operand[0]; a prior writer of s50 must get a RAW edge.
        _, t, g = _graph(".text\nk:\n  s_mov_b32 s50, 0\n"
                         "  s_cmp_lt_i32 s50, s76\n  s_endpgm\n")
        mov, cmp_ = _find(g, "s_mov"), _find(g, "s_cmp")
        self.assertTrue(_has_edge(g, mov, cmp_, EdgeType.RAW))
        # s_cmp must not be recorded as defining s50
        defs, _ = t.def_use("s_cmp_lt_i32", ["s50", "s76"])
        self.assertNotIn(("s", 50), defs)
        self.assertIn("scc", defs)

    def test_store_data_is_source(self):
        _, t, g = _graph(".text\nk:\n  v_mov_b32 v4, 0\n"
                         "  global_store_b32 v[2:3], v4, off\n  s_endpgm\n")
        mov, st = _find(g, "v_mov"), _find(g, "global_store")
        self.assertTrue(_has_edge(g, mov, st, EdgeType.RAW))   # store reads v4

    def test_smem_store_data_is_source(self):
        _, t, _ = _graph(".text\nk:\n  s_endpgm\n")
        defs, uses = t.def_use("s_store_dword", ["s4", "s[8:9]", "0x0"])
        self.assertNotIn(("s", 4), defs)   # s4 is the stored value (a use)
        self.assertIn(("s", 4), uses)

    def test_implicit_scc_chain(self):
        _, _, g = _graph(".text\nk:\n  s_add_u32 s16, s16, s51\n"
                         "  s_addc_u32 s17, s17, s52\n  s_endpgm\n")
        add, addc = _find(g, "s_add_u32"), _find(g, "s_addc")
        # s_add writes scc; s_addc reads (carry) and writes scc -> RAW on scc
        self.assertTrue(_has_edge(g, add, addc, EdgeType.RAW))


class TestMemAcc(unittest.TestCase):
    def test_store_then_load_orders(self):
        _, _, g = _graph(".text\nk:\n  global_store_b32 v[2:3], v4, off\n"
                         "  global_load_b32 v6, v[2:3], off\n  s_endpgm\n")
        st, ld = _find(g, "global_store"), _find(g, "global_load")
        self.assertTrue(_has_edge(g, st, ld, EdgeType.MEM))

    def test_load_load_reorderable(self):
        _, _, g = _graph(".text\nk:\n  global_load_b32 v6, v[8:9], off\n"
                         "  global_load_b32 v7, v[10:11], off\n  s_endpgm\n")
        l0, l1 = _find(g, "global_load", 0), _find(g, "global_load", 1)
        self.assertFalse(_has_edge(g, l0, l1, EdgeType.MEM))

    def test_mfma_acc_chain(self):
        _, _, g = _graph(".text\nk:\n"
                         "  v_mfma_f32_16x16x16_bf16 v[44:47], a[96:97], a[0:1], v[44:47]\n"
                         "  v_mfma_f32_16x16x16_bf16 v[44:47], a[98:99], a[2:3], v[44:47]\n"
                         "  s_endpgm\n")
        m0, m1 = _find(g, "v_mfma", 0), _find(g, "v_mfma", 1)
        self.assertTrue(_has_edge(g, m0, m1, EdgeType.ACC))


class TestM0Bundle(unittest.TestCase):
    def test_m0_edge_and_bundle(self):
        prog, t, g = _graph(".text\nk:\n  s_add_u32 m0, 0x100, s51\n"
                            "  buffer_load_dword v32, s[8:11], 0 offen lds\n  s_endpgm\n")
        setter, load = _find(g, "s_add_u32"), _find(g, "buffer_load")
        self.assertTrue(_has_edge(g, setter, load, EdgeType.M0))
        bundles = t.bundles(g.nodes)
        self.assertTrue(any(setter in b and load in b for b in bundles))


class TestFences(unittest.TestCase):
    def test_barrier_pins_and_blocks_crossing(self):
        _, _, g = _graph(".text\nk:\n  v_add_f32 v4, v2, v3\n  s_barrier\n"
                         "  v_add_f32 v5, v6, v7\n  s_endpgm\n")
        bar = _find(g, "s_barrier")
        a0, a1 = _find(g, "v_add", 0), _find(g, "v_add", 1)
        self.assertTrue(g.is_fence(bar))
        lo_bar, hi_bar = g.legal_window(bar)
        self.assertEqual((lo_bar, hi_bar), (g.by_iid[bar].pos, g.by_iid[bar].pos))
        # first add cannot move past the barrier; second cannot move before it
        self.assertLess(g.legal_window(a0)[1], g.by_iid[bar].pos)
        self.assertGreater(g.legal_window(a1)[0], g.by_iid[bar].pos)


class TestFixtureGraph(unittest.TestCase):
    def test_gemm_loop_graph(self):
        prog = parser.parse(_read(os.path.join(FIX, "gemm_style.s")))
        t = Gfx942Target.from_program(prog)
        a = regions.analyze(prog, t)
        loop = [r for r in a.regions if r.kind.value == "loop"][0]
        lines = regions.region_instr_lines(prog, loop)
        g = DepGraph.build(lines, t)
        self.assertTrue(g.edges())
        # the loop has an MFMA accumulator chain
        self.assertTrue(g.edges_of_type(EdgeType.ACC))
        for n in g.nodes:
            lo, hi = g.legal_window(n.iid)
            self.assertLessEqual(lo, n.pos)
            self.assertLessEqual(n.pos, hi)


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestRealKernelGraph(unittest.TestCase):
    """Per the request, exercise the dependency graph on the REAL kernel."""

    @classmethod
    def setUpClass(cls):
        cls.prog = parser.parse(_read(SHADER))
        cls.t = Gfx942Target.from_program(cls.prog)
        cls.a = regions.analyze(cls.prog, cls.t)

    def _region(self, kind):
        reg = [r for r in self.a.regions if r.kind.value == kind][0]
        lines = regions.region_instr_lines(self.prog, reg)
        return DepGraph.build(lines, self.t)

    def test_loop_graph_rich(self):
        g = self._region("loop")
        self.assertGreater(len(g.nodes), 100)
        # all edge categories that the loop must contain
        self.assertTrue(g.edges_of_type(EdgeType.RAW))
        self.assertTrue(g.edges_of_type(EdgeType.MEM))
        self.assertTrue(g.edges_of_type(EdgeType.M0))     # m0 + buffer_load lds
        self.assertTrue(g.edges_of_type(EdgeType.ACC))    # MFMA chain

    def test_legal_windows_self_consistent(self):
        for kind in ("prologue", "loop", "epilogue"):
            g = self._region(kind)
            for n in g.nodes:
                lo, hi = g.legal_window(n.iid)
                self.assertTrue(lo <= n.pos <= hi,
                                "window [{},{}] excludes pos {} in {}".format(
                                    lo, hi, n.pos, kind))

    def test_m0_bundles_pair_setter_with_lds_load(self):
        g = self._region("loop")
        bundles = self.t.bundles(g.nodes)
        self.assertTrue(bundles)
        # every bundle starts at an m0 writer and includes >=1 lds-load consumer
        for b in bundles:
            head = g.by_iid[b[0]]
            self.assertIn("m0", head.defs)
            self.assertTrue(any(
                self.t.is_lds_load(g.by_iid[i].line.opcode or "",
                                   g.by_iid[i].line.operands) for i in b[1:]))

    def test_mfma_writes_no_counter(self):
        # MFMA must NOT increment any memory counter (scoreboard-tracked)
        from reorder.model import WaitType
        for n in self._region("loop").nodes:
            op = n.line.opcode or ""
            if op.startswith("v_mfma") or op.startswith("v_smfmac"):
                self.assertEqual(self.t.wait_type(op, n.line.operands), WaitType.NONE)

    def test_fences_present(self):
        g = self._region("loop")
        self.assertTrue(g.fence_positions)  # waitcnt / barriers in the loop


if __name__ == "__main__":
    unittest.main()
