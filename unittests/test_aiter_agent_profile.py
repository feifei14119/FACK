"""Per-family aiter requirements and their evidence mapping, without GPU imports."""
from dataclasses import asdict
import importlib
from pathlib import Path

import pytest

import client
from client.aiter.agent_profile import validation_contract, result_evidence
from harness.validation import evidence
from harness.evaluator import EvalResult


ROOT = Path(__file__).resolve().parents[1]
DRIVERS = ROOT / 'client/aiter/hsa/gfx942'


@pytest.mark.parametrize('driver,family,expected', [
    ('optest_driver.py', None, ['constant/constant', 'uniform/auto']),
    ('dispatch_driver.py', 'blockscale', ['constant/constant', 'uniform/auto']),
    ('dispatch_driver.py', 'i8', ['signed_random/per_token']),
    ('gemm_driver.py', 'bf16', ['signed_random/none']),
    ('moe_stage1_driver.py', None, ['signed_random_routed/per_token']),
    ('mla_stage1_driver.py', None, ['signed_random_channel_mean/unit_tensor'])])
def test_per_family_metrics_are_declared_not_discovered_from_measurement(driver, family, expected):
    config = {'validation_hook': True, 'arch': 'gfx942', 'inputs': {'family': family}}
    contract = validation_contract(config, DRIVERS / driver)
    assert set(contract['metrics']) == {'hip_graph', *('op_test:' + x for x in expected)}
    config['dispatch'] = {'workload_id': 'fixed'}
    assert 'dispatch_matches_workload' in validation_contract(config, DRIVERS / driver)['required_checks']


def test_agent_does_not_silently_accept_graph_only_or_unknown_adapters():
    config = {'arch': 'gfx942', 'inputs': {}}
    with pytest.raises(ValueError, match='requires op_test'):
        validation_contract(config, DRIVERS / 'driver.py')
    config['validation_hook'] = True
    with pytest.raises(ValueError, match='no declared validation'):
        validation_contract(config, DRIVERS / 'unknown.py')
    config['arch'] = 'gfx1100'
    with pytest.raises(ValueError, match='not implemented'):
        validation_contract(config, DRIVERS / 'optest_driver.py')


def test_real_guidance_is_cpu_only_and_contains_aiter_and_architecture_skills():
    if not (ROOT / 'client/aiter/upstream/hsa/gfx942').is_dir():
        pytest.skip('pinned aiter submodule is not initialized')
    cl = client.resolve('aiter/hsa/gfx942')
    profile = cl.agent_profile(params=['--manifest', str(DRIVERS / 'optest_manifest.json')])
    assert profile['arch'] == 'gfx942'
    assert [s['role'] for s in profile['skills']] == ['client', 'client', 'architecture', 'architecture']
    assert profile['skills'][-1]['path'] == 'knowledge/skills/gfx942-scheduling-search/SKILL.md'
    assert set(profile['validation']['metrics']) == {'hip_graph', 'op_test:constant/constant', 'op_test:uniform/auto'}
    assert profile['workload']['source'] == 'explicit_manifest'
    assert cl.agent_profile()['client_profile_status'] == 'workload_unbound'
    with pytest.raises(ValueError, match='requires op_test'):
        cl.agent_profile(params=['--manifest', str(DRIVERS / 'manifest.json')])


def valid_report():
    return {'correct': True, 'time_us': 10, 'arch': 'gfx942', 'symbol': 'kernel',
            'co_sha256': 'co-hash', 'loader_observed': True,
            'checks': [{'case': name, 'passed': True} for name in ('seed+0', 'seed+1', 'after_graph_replay')],
            'op_test': {'correct': True, 'symbol': 'kernel', 'checks': [{'error_ratio': 0.0}],
                        'rows': [{'data_init': a, 'scale_init': b, 'asm err': 0, 'asm us': 12}
                                 for a, b in [('constant', 'constant'), ('uniform', 'auto')]]}}


@pytest.mark.parametrize('missing', ['distribution', 'full_output', 'loader', 'op_check', 'dispatch'])
def test_missing_aiter_evidence_fails_even_with_top_level_correct_true(missing):
    config = {'arch': 'gfx942', 'symbol': 'kernel', 'inputs': {}, 'validation_hook': True}
    contract = validation_contract(config, DRIVERS / 'optest_driver.py')
    report = valid_report()
    if missing == 'distribution': report['op_test']['rows'].pop()
    if missing == 'full_output': report['checks'].pop()
    if missing == 'loader': report['co_sha256'] = 'wrong'
    if missing == 'op_check': report['op_test']['checks'] = []
    if missing == 'dispatch':
        config['dispatch'] = {'workload_id': 'frozen'}
        contract = validation_contract(config, DRIVERS / 'optest_driver.py')
    normalized = result_evidence(config, report, {'status': 'consistent', 'artifact_after_build': {'sha256': 'co-hash'}})
    result = EvalResult(compiled=True, correct=True, tflops=100, detail={'validation': normalized})
    with pytest.raises(ValueError):
        evidence(asdict(result), contract)


def test_duplicate_distributions_are_rejected():
    report = valid_report()
    report['op_test']['rows'][1] = dict(report['op_test']['rows'][0])
    with pytest.raises(ValueError, match='duplicate'):
        result_evidence({'arch': 'gfx942', 'symbol': 'kernel'}, report, {})


def test_valid_aiter_evidence_and_compare_use_all_declared_distributions():
    from client.aiter.compare import metrics
    config = {'arch': 'gfx942', 'symbol': 'kernel', 'inputs': {}, 'validation_hook': True,
              'dispatch': {'workload_id': 'fixed', 'cu_num': 80, 'entrypoint': 'gemm', 'snapshot_sha256': 'snapshot'}}
    report = valid_report()
    report['dispatch_check'] = dict(config['dispatch'], correct=True)
    normalized = result_evidence(config, report, {'status': 'consistent', 'artifact_after_build': {'sha256': 'co-hash'}})
    sample = EvalResult(compiled=True, correct=True, tflops=100, detail={'validation': normalized})
    contract = validation_contract(config, DRIVERS / 'optest_driver.py')
    assert metrics(sample, contract) == {'hip_graph': 10, 'op_test:constant/constant': 12, 'op_test:uniform/auto': 12}
    del sample.detail['validation']['metrics']['op_test:uniform/auto']
    with pytest.raises(ValueError, match='missing'):
        metrics(sample, contract)


@pytest.mark.parametrize('check', [{'passed': False, 'error_ratio': 0}, {'passed': True, 'error_ratio': 0.1},
                                  {'error_ratio': False}, {}])
def test_explicit_optest_failure_cannot_be_overridden(check):
    report = valid_report()
    report['op_test']['checks'] = [check]
    normalized = result_evidence({'arch': 'gfx942', 'symbol': 'kernel'}, report, {})
    assert normalized['checks']['op_test'] is False


def test_planning_does_not_load_aiter_manifest_or_dependencies(monkeypatch):
    module = importlib.import_module('client.aiter.agent_profile')
    monkeypatch.setattr(module, 'options', lambda ctx: pytest.fail('planning must not read a workload'))
    ctx = client.ClientContext('aiter/hsa/gfx942', 'aiter', 'hsa/gfx942', '', '', '')
    profile = module.agent_profile(ctx)
    assert profile['requires_workload'] is True
    assert profile['validation'] is None
    assert profile['skills'][0] == 'knowledge/skills/aiter-tuning/SKILL.md'
