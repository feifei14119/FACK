"""M1 tests: CFG / region splitting + metadata-label fix."""
import os
import unittest

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.model import LineKind

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SHADER = os.path.join(os.path.dirname(__file__), os.pardir, "client", "poc_kl", "fp8_blockscale_gemm", "shader",
                      "fp8gemm_blockscase_32mx1_32nx4.s")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return parser.parse(f.read())


class TestRegionsFixture(unittest.TestCase):
    def setUp(self):
        self.prog = _load(os.path.join(FIX, "gemm_style.s"))
        self.t = Gfx942Target.from_program(self.prog)

    def test_loop_detected(self):
        a = regions.analyze(self.prog, self.t)
        loops = [lp.header_label for lp in a.loops]
        self.assertIn("label_0338", loops)

    def test_region_kinds_order(self):
        a = regions.analyze(self.prog, self.t)
        kinds = [r.kind.value for r in a.regions]
        self.assertIn("loop", kinds)
        self.assertIn("prologue", kinds)
        # epilogue (label_00B0 .. s_endpgm) comes after the loop
        self.assertEqual(kinds[-1], "epilogue")

    def test_text_only_no_rodata(self):
        # code items must not include .rodata / metadata lines
        a = regions.analyze(self.prog, self.t)
        for it in a.items:
            self.assertIn(it.line.kind, (LineKind.INSTR, LineKind.LABEL))


class TestMetadataFix(unittest.TestCase):
    def test_metadata_not_label(self):
        text = (".amdgpu_metadata\n"
                "---\n"
                "amdhsa.kernels:\n"
                "  - .name: k\n"
                ".end_amdgpu_metadata\n")
        prog = parser.parse(text)
        # 'amdhsa.kernels:' would match the label regex but must be OTHER here
        kinds = {ln.raw.strip(): ln.kind for ln in prog.lines}
        self.assertEqual(kinds["amdhsa.kernels:"], LineKind.OTHER)
        self.assertEqual(kinds[".amdgpu_metadata"], LineKind.DIRECTIVE)
        self.assertEqual(kinds[".end_amdgpu_metadata"], LineKind.DIRECTIVE)
        # losslessness preserved
        from reorder import emitter
        self.assertEqual(emitter.emit(prog), text)


@unittest.skipUnless(os.path.exists(SHADER), "real testcase shader not present")
class TestRegionsRealShader(unittest.TestCase):
    def setUp(self):
        self.prog = _load(SHADER)
        self.t = Gfx942Target.from_program(self.prog)

    def test_analyze_runs(self):
        a = regions.analyze(self.prog, self.t)
        self.assertTrue(a.items)
        self.assertTrue(a.blocks)
        # the kernel has back-edge loops (s_cbranch_scc0/1 to earlier labels)
        self.assertTrue(a.loops)

    def test_no_metadata_labels(self):
        # after the fix, 'amdhsa.kernels:' inside metadata is not a LABEL
        labels = [ln.label for ln in self.prog.label_lines()]
        self.assertNotIn("amdhsa.kernels", labels)


if __name__ == "__main__":
    unittest.main()
