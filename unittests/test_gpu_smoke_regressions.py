"""CPU regressions for failures found during the gfx942 aiter smoke run."""
from contextlib import redirect_stdout
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import co2s, eval_candidate


class TestDescriptorRoundtrip(unittest.TestCase):
    def test_88_sgpr_xnack_decode_preserves_granule_and_explicit_footprint(self):
        lines = ['.amdhsa_next_free_sgpr 88', '.amdhsa_reserve_xnack_mask 1',
                 '.amdhsa_reserve_vcc 0']
        insts = [{'orig': 's_load_dwordx4 s[72:75], s[2:3], 0'},
                 {'orig': 's_mov_b32 s76, s0'}]
        for target in ('gfx942', 'gfx942:xnack+'):
            changed = co2s.normalize_88_sgpr_descriptor(target, lines, insts, '  .sgpr_count: 77\n')
            self.assertIn('.amdhsa_next_free_sgpr 77', changed)
            # The actual LLVM rebuild must verify the encoded allocation;
            # this CPU check only proves the explicit footprint is retained.
        self.assertEqual(lines[0], '.amdhsa_next_free_sgpr 88')

    def test_88_sgpr_normalization_requires_complete_footprint_evidence(self):
        lines = ['.amdhsa_next_free_sgpr 88', '.amdhsa_reserve_xnack_mask 1',
                 '.amdhsa_reserve_vcc 0']
        cases = [
            ('gfx942:xnack-', lines, [{'orig': 's_mov_b32 s76, 0'}], '.sgpr_count: 77'),
            ('gfx950', lines, [{'orig': 's_mov_b32 s76, 0'}], '.sgpr_count: 77'),
            ('gfx942', lines[:-1], [{'orig': 's_mov_b32 s76, 0'}], '.sgpr_count: 77'),
            ('gfx942', lines, [{'orig': 's_load_dwordx4 s[82:85], s[2:3], 0'}], '.sgpr_count: 77'),
            ('gfx942', lines, [{'orig': 's_mov_b32 s76, 0'}], '.sgpr_count: 88'),
            ('gfx942', lines, [{'orig': 's_mov_b32 s76, 0', 'raw': [0]}], '.sgpr_count: 77'),
            ('gfx942', lines, [{'orig': 's_mov_b32 s76, 0'}], ''),
        ]
        for target, block, insts, metadata in cases:
            with self.subTest(target=target, insts=insts, metadata=metadata):
                self.assertEqual(co2s.normalize_88_sgpr_descriptor(target, block, insts, metadata), block)

    def test_gfx942_112_sgpr_granule_is_only_normalized_with_xnack(self):
        decoded = '.amdhsa_kernel k\n.amdhsa_reserve_xnack_mask 1\n.amdhsa_next_free_sgpr 112\n.end_amdhsa_kernel\n'
        for target, expected in [('gfx942',102),('gfx942:xnack+',102),('gfx942:xnack-',112),('gfx950',112)]:
            with self.subTest(target=target), patch.object(co2s,'tool',side_effect=lambda x:x), patch.object(co2s,'run',return_value=decoded):
                self.assertIn('.amdhsa_next_free_sgpr '+str(expected),co2s.kernel_descriptor(target,'original.co','k.kd'))
        self.assertEqual((102+4-1)//8,(112-1)//8)

    def test_gfx942_last_sgpr_granule_and_xnack_mode(self):
        for target, reservation, next_free, attr in (
            ('gfx942', 1, 98, '+xnack'),
            ('gfx942:xnack+', 1, 98, '+xnack'),
            ('gfx942:xnack-', 0, 102, '-xnack'),
        ):
            decoded = ('.amdhsa_kernel k\n'
                       '.amdhsa_reserve_xnack_mask {}\n'
                       '.amdhsa_next_free_sgpr 104\n'
                       '.end_amdhsa_kernel\n').format(reservation)
            with self.subTest(target=target), patch.object(co2s, 'tool', side_effect=lambda x:x), \
                    patch.object(co2s, 'run', return_value=decoded) as run:
                lines = co2s.kernel_descriptor(target, 'original.co', 'k.kd')
                self.assertIn('--mcpu=gfx942', run.call_args[0][0])
                self.assertIn('--mattr='+attr, run.call_args[0][0])
                self.assertIn('.amdhsa_next_free_sgpr '+str(next_free), lines)
                # XNACK reserves four SGPRs on gfx9. Keep the original 104-SGPR
                # allocation granule without emitting an out-of-range operand.
                total = next_free + (4 if reservation else 0)
                self.assertEqual((total - 1) // 8, (104 - 1) // 8)


class TestEvaluationExitStatus(unittest.TestCase):
    def test_failed_or_missing_correctness_is_a_cli_failure(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)/'seed.s'
            source.write_text('seed')
            for correct in (False, None, True):
                result = SimpleNamespace(compiled=True, correct=correct,
                                         detail={'error':'runner failed'},
                                         tflops=2.0 if correct else None,
                                         time_us=3.0 if correct else None)
                evaluator = SimpleNamespace(evaluate=lambda *a,**kw:result)
                cl = SimpleNamespace(spec='test',make_evaluator=lambda **kw:evaluator)
                output = io.StringIO()
                with self.subTest(correct=correct), patch.object(eval_candidate._clients,'resolve',return_value=cl), \
                        patch.object(eval_candidate.sys,'argv',['eval_candidate.py',str(source),'--client','test']), \
                        redirect_stdout(output):
                    code = eval_candidate.main()
                self.assertEqual(code,0 if correct else 1)
                if not correct:
                    self.assertIn('runner failed',output.getvalue())
                    self.assertNotIn('perf      :',output.getvalue())


if __name__ == '__main__':
    unittest.main()
