"""M0 acceptance: lossless parse->emit round-trip + sane lexical classification.

Run (zero install):  cd testft && python3.8 -m unittest discover -s unittests -t . -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# Make the project root (testft/) importable when run via plain unittest.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import reorder  # noqa: E402
from reorder.lexer import find_comment, split_operands  # noqa: E402
from reorder.model import LineKind  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURES = ["gemm_style.s", "kvadd_style.s"]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


class RoundTripTest(unittest.TestCase):
    def test_emit_is_byte_identical_for_fixtures(self):
        for name in FIXTURES:
            path = os.path.join(FIX, name)
            text = _read(path)
            prog = reorder.parse(text)
            out = reorder.emit(prog)
            self.assertEqual(out, text, "emit() not byte-identical for %s" % name)

    def test_write_reproduces_file_exactly(self):
        for name in FIXTURES:
            path = os.path.join(FIX, name)
            with open(path, "rb") as f:
                original_bytes = f.read()
            prog = reorder.parse_file(path)
            with tempfile.NamedTemporaryFile("w+b", suffix=".s", delete=False) as tf:
                tmp = tf.name
            try:
                reorder.write(prog, tmp)
                with open(tmp, "rb") as f:
                    written_bytes = f.read()
                self.assertEqual(written_bytes, original_bytes,
                                 "write() not byte-identical for %s" % name)
            finally:
                os.unlink(tmp)

    def test_synthetic_edge_cases_round_trip(self):
        cases = [
            "",                       # empty file
            "\n",                     # single newline
            "abc",                    # no trailing newline
            "a\nb\nc",                # no trailing newline, multi-line
            "a\nb\n",                 # trailing newline
            "line1\r\nline2\r\n",     # CRLF preserved
            "\n\n\n",                 # only blanks
            "  s_nop 0  ",            # trailing spaces, no newline
        ]
        for text in cases:
            prog = reorder.parse(text)
            self.assertEqual(reorder.emit(prog), text, "round-trip failed for %r" % text)


class ClassificationTest(unittest.TestCase):
    def setUp(self):
        self.gemm = reorder.parse_file(os.path.join(FIX, "gemm_style.s"))
        self.kvadd = reorder.parse_file(os.path.join(FIX, "kvadd_style.s"))

    def test_gemm_labels(self):
        names = [ln.label for ln in self.gemm.label_lines()]
        for expected in ("label_005F", "label_0338", "label_00B0"):
            self.assertIn(expected, names)

    def test_gemm_instructions_present(self):
        opcodes = {ln.opcode for ln in self.gemm.instr_lines()}
        for op in ("v_mfma_f32_16x16x16_bf16", "buffer_load_dword",
                   "ds_read_b128", "s_waitcnt", "s_barrier", "s_endpgm"):
            self.assertIn(op, opcodes)

    def test_gemm_mfma_operands_preserve_brackets(self):
        mfma = [ln for ln in self.gemm.instr_lines()
                if ln.opcode == "v_mfma_f32_16x16x16_bf16"][0]
        self.assertEqual(mfma.operands, ["v[44:47]", "a[96:97]", "a[0:1]", "v[44:47]"])

    def test_gemm_directives_present(self):
        directives = {ln.directive for ln in self.gemm.lines
                      if ln.kind is LineKind.DIRECTIVE}
        for d in (".text", ".global", ".amdhsa_kernel", ".amdgpu_metadata"):
            self.assertIn(d, directives)

    def test_kvadd_dot_label_is_label_not_directive(self):
        names = [ln.label for ln in self.kvadd.label_lines()]
        self.assertIn(".label_exit", names)
        self.assertIn("vadd_kernel", names)

    def test_kvadd_set_lines_are_directives(self):
        sets = [ln for ln in self.kvadd.lines
                if ln.kind is LineKind.DIRECTIVE and ln.directive == ".set"]
        self.assertGreaterEqual(len(sets), 5)

    def test_kvadd_trailing_comment_captured(self):
        load = [ln for ln in self.kvadd.instr_lines() if ln.opcode == "s_load_b64"][0]
        self.assertIsNotNone(load.comment)
        self.assertIn("load base ptr", load.comment)
        # operands must not include the comment
        self.assertEqual(load.operands, ["s[s_karg:s_karg+1]", "s[0:1]", "0x18"])

    def test_kvadd_whole_line_comment(self):
        comments = [ln for ln in self.kvadd.lines if ln.kind is LineKind.COMMENT]
        self.assertTrue(any("kernarg layout" in (c.comment or "") for c in comments))

    def test_kvadd_global_load_operand_split(self):
        gl = [ln for ln in self.kvadd.instr_lines() if ln.opcode == "global_load_b32"][0]
        self.assertEqual(gl.operands, ["v[v_a]", "v[2:3]", "off"])


class LexerHelperTest(unittest.TestCase):
    def test_find_comment_ignores_brackets(self):
        self.assertEqual(find_comment("ds_read_b128 a[0:3], v31"), -1)
        self.assertGreater(find_comment("s_nop 0 // pad"), 0)
        self.assertGreater(find_comment("s_endpgm ; done"), 0)

    def test_split_operands_top_level_commas(self):
        self.assertEqual(split_operands("v[44:47], a[96:97], a[0:1], v[44:47]"),
                         ["v[44:47]", "a[96:97]", "a[0:1]", "v[44:47]"])
        self.assertEqual(split_operands("v32, s[8:11], 0 offen lds"),
                         ["v32", "s[8:11]", "0 offen lds"])
        self.assertEqual(split_operands(""), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
