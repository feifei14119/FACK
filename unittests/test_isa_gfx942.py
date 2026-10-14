"""M1 tests: gfx942 operand model, classifier, counter model, registry."""
import os
import unittest

from isa import registry
from isa.gfx942.target import Gfx942Target
from isa.gfx942 import operands as ops
from isa.gfx942.counters import Gfx942CounterModel
from reorder.model import Kind, WaitType
from reorder import parser

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestOperands(unittest.TestCase):
    def test_single_and_range(self):
        self.assertEqual(ops.parse_token("v5"), {("v", 5)})
        self.assertEqual(ops.parse_token("s[8:11]"),
                         {("s", 8), ("s", 9), ("s", 10), ("s", 11)})

    def test_acc_is_agpr(self):
        # 'acc[0:1]' and 'a[0:1]' must normalize to the same AGPR units
        self.assertEqual(ops.parse_token("acc[0:1]"), {("a", 0), ("a", 1)})
        self.assertEqual(ops.parse_token("acc48"), {("a", 48)})
        self.assertEqual(ops.parse_token("a96"), {("a", 96)})

    def test_special_and_immediate(self):
        self.assertEqual(ops.parse_token("m0"), {"m0"})
        self.assertEqual(ops.parse_token("vcc_lo"), {"vcc"})
        self.assertEqual(ops.parse_token("exec"), {"exec"})
        self.assertEqual(ops.parse_token("0x100"), set())
        self.assertEqual(ops.parse_token("null"), set())
        self.assertEqual(ops.parse_token("off"), set())

    def test_alias_expansion(self):
        aliases = {"s_karg": 0}
        self.assertEqual(ops.parse_token("s[s_karg:s_karg+1]", aliases),
                         {("s", 0), ("s", 1)})

    def test_field_takes_leading_token_only(self):
        # '0 offen lds' -> immediate 0, modifiers ignored for registers
        self.assertEqual(ops.parse_operand_field("0 offen lds"), set())

    def test_regset_overlap(self):
        a = ops.RegSet({("v", 36), ("v", 37)})
        b = ops.RegSet({("v", 37)})
        c = ops.RegSet({("v", 40)})
        self.assertTrue(a.overlaps(b))
        self.assertFalse(a.overlaps(c))


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.t = Gfx942Target()

    def _k(self, opcode, operands=None):
        return self.t.classify(opcode, operands or [])

    def test_mfma(self):
        self.assertEqual(self._k("v_mfma_f32_16x16x32_fp8_fp8"), Kind.MFMA)
        self.assertEqual(self.t.wait_type("v_mfma_f32_16x16x16_bf16", []), WaitType.NONE)

    def test_mem_kinds(self):
        self.assertEqual(self._k("buffer_load_dword", ["v32", "s[8:11]", "0 offen lds"]),
                         Kind.VMEM_LOAD)
        self.assertEqual(self._k("global_store_b32", ["v[2:3]", "v4", "off"]),
                         Kind.VMEM_STORE)
        self.assertEqual(self.t.wait_type("global_store_b32", []), WaitType.VS)
        self.assertEqual(self._k("ds_read_b128", ["a[0:3]", "v31"]), Kind.DS_READ)
        self.assertEqual(self._k("ds_write_b128", ["v31", "v[44:47]"]), Kind.DS_WRITE)
        self.assertEqual(self._k("s_load_dwordx2", ["s[16:17]", "s[0:1]", "0x0"]), Kind.SMEM)

    def test_lds_load_flag(self):
        self.assertTrue(self.t.is_lds_load("buffer_load_dword", ["v32", "s[8:11]", "0 offen lds"]))
        self.assertFalse(self.t.is_lds_load("buffer_load_dword", ["v32", "s[8:11]", "0 offen"]))

    def test_set_m0(self):
        self.assertEqual(self._k("s_add_u32", ["m0", "0", "s58"]), Kind.SET_M0)

    def test_control(self):
        self.assertEqual(self._k("s_waitcnt", ["vmcnt(0)"]), Kind.WAITCNT)
        self.assertEqual(self._k("s_barrier"), Kind.BARRIER)
        self.assertEqual(self._k("s_nop", ["0"]), Kind.NOP)
        self.assertEqual(self._k("s_cbranch_scc0", ["label_x"]), Kind.BRANCH)
        self.assertEqual(self._k("s_branch", ["label_x"]), Kind.BRANCH)

    def test_alu(self):
        self.assertEqual(self._k("v_add_f32_e32", ["v4", "v2", "v3"]), Kind.VALU)
        self.assertEqual(self._k("s_cmp_eq_u32", ["s53", "0"]), Kind.SALU)


class TestCounterModel(unittest.TestCase):
    def setUp(self):
        self.cm = Gfx942CounterModel()

    def test_symbolic_ampersand(self):
        spec = self.cm.parse_wait("s_waitcnt", ["vmcnt(10) & lgkmcnt(0)"])
        self.assertEqual(spec.targets["vm"], 10)
        self.assertEqual(spec.targets["lgkm"], 0)
        self.assertIsNone(spec.targets.get("exp"))

    def test_symbolic_space(self):
        spec = self.cm.parse_wait("s_waitcnt", ["vmcnt(20) lgkmcnt(0)"])
        self.assertEqual(spec.targets["vm"], 20)
        self.assertEqual(spec.targets["lgkm"], 0)

    def test_plain_single(self):
        spec = self.cm.parse_wait("s_waitcnt", ["lgkmcnt(0)"])
        self.assertEqual(spec.targets["lgkm"], 0)
        self.assertNotIn("vm", spec.targets)

    def test_numeric_simm16(self):
        # 0x0000 -> wait everything to 0
        spec = self.cm.parse_wait("s_waitcnt", ["0x0000"])
        self.assertEqual(spec.targets["vm"], 0)
        self.assertEqual(spec.targets["lgkm"], 0)
        self.assertEqual(spec.targets["exp"], 0)

    def test_simm16_roundtrip(self):
        for vm, lgkm, exp in [(0, 0, 0), (10, 0, 7), (63, 15, 7), (5, 3, 1)]:
            enc = self.cm._encode_simm16(vm, lgkm, exp)
            dec = self.cm._decode_simm16(enc)
            self.assertEqual((dec["vm"], dec["lgkm"], dec["exp"]), (vm, lgkm, exp))

    def test_vscnt(self):
        spec = self.cm.parse_wait("s_waitcnt_vscnt", ["null", "0"])
        self.assertEqual(spec.targets["vs"], 0)


class TestRegistry(unittest.TestCase):
    def test_lazy_get(self):
        t = registry.get("gfx942")
        self.assertEqual(t.name, "gfx942")
        self.assertIn("gfx942", registry.available())

    def test_unknown(self):
        with self.assertRaises(KeyError):
            registry.get("gfxNOPE")

    def test_from_program_aliases(self):
        with open(os.path.join(FIX, "kvadd_style.s"), encoding="utf-8") as f:
            prog = parser.parse(f.read())
        t = Gfx942Target.from_program(prog)
        self.assertEqual(t._aliases.get("s_karg"), 0)
        self.assertEqual(t._aliases.get("v_c"), 4)
        defs, uses = t.parse_operands("s_load_b64",
                                      ["s[s_karg:s_karg+1]", "s[0:1]", "0x18"])
        self.assertEqual(defs.units, {("s", 0), ("s", 1)})


if __name__ == "__main__":
    unittest.main()
