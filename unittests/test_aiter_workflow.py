"""Portable workflow regressions; fake Docker/torch/aiter, no GPU or compiler."""
from contextlib import nullcontext, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from client.aiter import docker_env, runner, compare
from client.aiter.hsa.gfx942 import optest_driver
from harness.evaluator import EvalResult


class TestDockerSelection(unittest.TestCase):
    def test_physical_selection_is_sorted_and_uuid_based(self):
        rows = {'card{}'.format(i): {'PCI Bus': '0001:{:02x}:00.0'.format(i),
                'Unique ID': hex(i+100), 'GFX Version':'gfx942'} for i in (3, 0, 2, 1)}
        devices = docker_env.parse_inventory(rows)
        selected = docker_env.select_gpu(devices, 'second-last', 'gfx942')
        self.assertEqual(selected['index'], 2)
        for key in ('2', selected['pci'], selected['uuid']):
            self.assertEqual(docker_env.select_gpu(devices, key, 'gfx942'), selected)
        with self.assertRaises(ValueError):
            docker_env.select_gpu(devices[:1], 'second-last', 'gfx942')
        repo = Path('/tmp/a repo with spaces')
        argv = docker_env.build_start_command(repo, 'sha256:pinned', 'test', selected,
                                             repo/'client/aiter/tune_out/env', 4, [44, 44])
        self.assertIn('ROCR_VISIBLE_DEVICES='+selected['uuid'], argv)
        self.assertIn('HIP_VISIBLE_DEVICES=0', argv)
        self.assertTrue(any(arg.startswith('TORCHINDUCTOR_CACHE_DIR=/workspace/FACK/client/aiter/tune_out/') for arg in argv))
        self.assertTrue(any(arg.startswith('USER=') for arg in argv))
        self.assertIn('type=bind,src=/tmp/a repo with spaces,dst=/workspace/FACK', argv)
        self.assertEqual(argv.count('--group-add'), 1)
        self.assertIn('sha256:pinned', argv)

    def test_inherited_masks_fail_before_any_docker_action(self):
        with patch.dict(docker_env.os.environ, {'HIP_VISIBLE_DEVICES':'1'}), \
                patch.object(docker_env, 'command') as command:
            with self.assertRaisesRegex(ValueError, 'visibility restrictions'):
                docker_env.start(SimpleNamespace())
            command.assert_not_called()

    def test_stop_rejects_foreign_container(self):
        info = [{'Config':{'Labels':{'unrelated':'1'}}}]
        with patch.object(docker_env,'command',return_value=json.dumps(info)) as cmd, \
                patch('sys.stderr',new=io.StringIO()):
            self.assertEqual(docker_env.main(['stop','other-user-container']),1)
            self.assertEqual(cmd.call_count,1)


class TestOpTestStage(unittest.TestCase):
    def test_definition_loader_does_not_execute_cli_and_rejects_drift(self):
        source = b'def test_gemm():\n    return 42\nparser = object()\nraise RuntimeError("CLI executed")\n'
        with tempfile.TemporaryDirectory(prefix='optest space ') as td:
            path=Path(td)/'test.py'; path.write_bytes(source)
            namespace={}
            exec(optest_driver.definitions(path,hashlib.sha256(source).hexdigest()),namespace)
            self.assertEqual(namespace['test_gemm'](),42)
            path.write_bytes(source+b'\n# changed\n')
            with self.assertRaisesRegex(ValueError,'changed'):
                optest_driver.definitions(path,hashlib.sha256(source).hexdigest())

    def test_explicit_hook_runs_once_for_nondefault_seed(self):
        calls=[]
        driver=SimpleNamespace(validate=lambda inputs,symbol,seed: calls.append(seed) or {'correct':True})
        runner.validate_driver(driver,{'inputs':{},'symbol':'k','seed':987})
        self.assertEqual(calls,[987])
        with self.assertRaises(ValueError):
            runner.validate_driver(SimpleNamespace(),{'inputs':{},'symbol':'k','seed':987})

    def test_validate_pins_symbol_checks_all_paths_and_restores_on_failure(self):
        source = '''
def checkAllclose(*args, **kwargs):
    return FAILURE_RATIO

def test_gemm(dtype,m,n,k,**kwargs):
    import aiter
    aiter.gemm_a8w8_blockscale_bpreshuffle_asm('x',kernelName='wrong',splitK=7)
    for label in ['ck','ck strided x_scale','asm','triton']:
        checkAllclose('a','b',msg=label)
    return dict(dtype=dtype, data_init=kwargs['data_init'], scale_init=kwargs['scale_init'],
                seed=kwargs['seed'], **{'asm err':0,'ck err':0,'triton err':0,
                                      'asm us':5.0,'ck us':7.0,'triton us':8.0})
'''
        for fail in (0, 0.01):
            calls=[]
            original=lambda *a,**kw: calls.append(kw)
            aiter=SimpleNamespace(gemm_a8w8_blockscale_bpreshuffle_asm=original,
                                  gemm_a8w8_blockscale_bpreshuffle=original,dtypes=SimpleNamespace(bf16='bf16'))
            torch=SimpleNamespace(isfinite=lambda a:SimpleNamespace(all=lambda:SimpleNamespace(item=lambda:True)))
            code=compile('FAILURE_RATIO='+str(fail)+'\n'+source,'fake.py','exec')
            with patch.dict('sys.modules',{'aiter':aiter,'torch':torch}), \
                    patch.object(optest_driver,'definitions',return_value=code):
                if fail:
                    with self.assertRaisesRegex(ValueError,'comparison failed'):
                        optest_driver.validate({'m':256,'n':256,'k':1024},optest_driver.SYMBOL,987)
                else:
                    result=optest_driver.validate({'m':256,'n':256,'k':1024},optest_driver.SYMBOL,987)
                    self.assertEqual([r['seed'] for r in result['rows']],[987,987])
                    self.assertEqual(len(result['checks']),8)
            self.assertIs(aiter.gemm_a8w8_blockscale_bpreshuffle_asm,original)
            self.assertTrue(all(c['kernelName']==optest_driver.SYMBOL and c['splitK']==1 for c in calls))

    def test_missing_and_nonfinite_metrics_cannot_pass(self):
        for value in (None,float('nan'),-1,0):
            row={'asm err':0,'ck err':0,'triton err':0,'asm us':value,'ck us':1,'triton us':1}
            with self.assertRaises(ValueError):optest_driver.validate_row(row)


class TestPairedWorkflow(unittest.TestCase):
    def test_failure_is_preserved_and_stops_before_candidate(self):
        with tempfile.TemporaryDirectory(prefix='compare space ') as td:
            p=Path(td);(p/'base.s').write_text('seed');(p/'other.s').write_text('candidate')
            count=[]
            evaluator=SimpleNamespace(evaluate=lambda path: count.append(path) or EvalResult(compiled=True,correct=False))
            cl=SimpleNamespace(out_dir=str(p),spec='aiter/hsa/gfx942',make_evaluator=lambda **kw:evaluator)
            args=SimpleNamespace(client=cl.spec,baseline=p/'base.s',candidate=p/'other.s',pairs=6,min_gain=.01,alpha=.05,loop=10)
            contract={'client_identity':{'status':'available'}}
            with patch.object(compare.clients,'resolve',return_value=cl), \
                    patch.object(compare,'client_contract',return_value=contract), \
                    patch.object(compare,'evaluation_lock',return_value=nullcontext()),redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'correctness'):
                    compare.compare(args,[])
            self.assertEqual(len(count),1)
            report=json.loads(next((p/'comparisons').glob('*/comparison.json')).read_text())
            self.assertEqual(report['status'],'failed')
            self.assertEqual(report['records'][0]['result']['correct'],False)

    def test_different_timing_methods_are_assessed_separately(self):
        records=[{'trial':i,'side':side,'times_us':{'hip_graph':10 if side=='reference' else 12,
                   'op_test:uniform/auto':10 if side=='reference' else 8}} for i in range(6) for side in ('reference','candidate')]
        policy={'method':'paired_sign_v1','confirm_pairs':6,'final_pairs':6,'min_gain':.01,'alpha':.05,'max_confirmations':1}
        summary=compare.summarize(records,policy)
        self.assertEqual(summary['hip_graph']['verdict'],'regression')
        self.assertEqual(summary['op_test:uniform/auto']['verdict'],'confirmed_gain')
        with self.assertRaises(ValueError):compare.summarize(records[:-1],policy)


if __name__ == '__main__':
    unittest.main()
