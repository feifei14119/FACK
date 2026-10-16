"""All declared metrics/checks are mandatory, including secondary regressions."""
import copy

import pytest

from agent.run import RunController
from harness.comparison import pair_order
from harness.evaluator import EvalResult
from harness.validation import evidence
from tools.tune_run_report import snapshot_report, render_markdown
from unittests.test_paired_validation import POLICY
from unittests.test_tuning_run import FakeEvaluator, prepare
from unittests.test_session import _SYNTH


VALIDATION = {'metrics': {'benchmark': {'unit': 'us', 'direction': 'lower'},
                          'tail': {'unit': 'us', 'direction': 'lower'}},
              'primary_metric': 'benchmark', 'required_checks': ['full_output'],
              'recommendation_scope': 'workload', 'associated_workloads': 'not_applicable'}


def result(first=10, second=20):
    return EvalResult(compiled=True, correct=True, tflops=1000 / first, time_us=first,
                      detail={'validation': {'metrics': {'benchmark': first, 'tail': second},
                                             'checks': {'full_output': True}}})


def paired(first=5, second=10):
    return FakeEvaluator(*(result() if side == 'reference' else result(first, second)
                           for i in range(8) for side in pair_order(i)))


@pytest.fixture
def ready(tmp_path):
    contract = {'client': 'custom', 'params': [], 'agent_profile': {'validation': VALIDATION}}
    run = RunController.create(tmp_path / 'run', _SYNTH, contract, perf_repeats=1,
                               eval_call_limit=100, final_eval_reserve=16, comparison_policy=POLICY,
                               protect_prefetch=False)
    run.evaluate('original', FakeEvaluator(result()))
    cid = prepare(run)['candidate_id']
    run.evaluate(cid, FakeEvaluator(result(5, 10)))
    return run, cid


@pytest.mark.parametrize('change', ['missing_metric', 'extra_metric', 'missing_check', 'false_check', 'nan'])
def test_bad_client_evidence_cannot_pass_screening(tmp_path, change):
    contract = {'client': 'custom', 'agent_profile': {'validation': VALIDATION}}
    run = RunController.create(tmp_path/'run', _SYNTH, contract, perf_repeats=1)
    sample = result()
    data = sample.detail['validation']
    if change == 'missing_metric': del data['metrics']['tail']
    if change == 'extra_metric': data['metrics']['new'] = 1
    if change == 'missing_check': data['checks'].clear()
    if change == 'false_check': data['checks']['full_output'] = False
    if change == 'nan': data['metrics']['tail'] = float('nan')
    batch = run.evaluate('original', FakeEvaluator(sample))
    assert batch['status'] == 'measurement_invalid'
    state = run.status()['state']
    attempt = next(iter(state['attempts'].values()))
    assert attempt['result']['correct'] is True  # raw evidence is retained
    assert attempt['validation']['status'] == 'failed'
    assert state['used']['eval_calls'] == 1


def test_primary_gain_cannot_hide_secondary_regression(ready):
    run, cid = ready
    compared = run.confirm(cid, paired(5, 40))
    assert compared['analysis']['verdict'] == 'confirmed_gain'
    assert compared['methods']['tail']['verdict'] == 'regression'
    assert compared['verdict'] == 'regression'
    assert run.status()['state']['incumbent_id'] is None
    assert run.finalize(FakeEvaluator())['status'] == 'original_retained'


def test_all_metrics_confirm_and_fresh_final_with_report(ready):
    run, cid = ready
    assert run.confirm(cid, paired())['verdict'] == 'confirmed_gain'
    final = run.finalize(paired())
    assert final['status'] == 'final_recommended'
    assert final['recommendation_scope'] == 'workload'
    assert final['artifact_adoption'] == 'not_assessed'
    assert set(final['methods']) == {'benchmark', 'tail'}
    report = snapshot_report(run.directory)
    assert report['final_vs_original_methods'] == final['methods']
    assert report['recommendation']['id'] == cid
    assert 'tail' in render_markdown(report)
    assert run.status()['state']['used']['eval_calls'] == 34


def test_final_secondary_failure_revokes_candidate(ready):
    run, cid = ready
    run.confirm(cid, paired())
    assert run.finalize(paired(5, 40))['status'] == 'original_retained'
    assert snapshot_report(run.directory)['recommendation'] is None


def test_missing_final_metric_is_incomplete_not_a_gain(ready):
    run, cid = ready
    run.confirm(cid, paired())
    broken = result()
    del broken.detail['validation']['metrics']['tail']
    final = run.finalize(FakeEvaluator(broken))
    assert final['status'] == 'original_retained'
    assert final['reason'] == 'measurement_invalid'


def test_client_can_use_a_single_non_time_metric_without_csv_or_optest(tmp_path):
    contract = copy.deepcopy(VALIDATION)
    contract.update(metrics={'throughput': {'unit': 'items/s', 'direction': 'higher'}}, primary_metric='throughput')
    declared = {'client': 'another', 'agent_profile': {'validation': contract}}
    run = RunController.create(tmp_path/'run', _SYNTH, declared, perf_repeats=1,
                               eval_call_limit=100, final_eval_reserve=16, comparison_policy=POLICY)
    def item(score):
        return EvalResult(compiled=True, correct=True, tflops=score,
                          detail={'validation': {'metrics': {'throughput': score}, 'checks': {'full_output': True}}})
    run.evaluate('original', FakeEvaluator(item(100)))
    cid = prepare(run)['candidate_id']
    run.evaluate(cid, FakeEvaluator(item(200)))
    samples = lambda: FakeEvaluator(*(item(100 if side == 'reference' else 200)
                                      for i in range(8) for side in pair_order(i)))
    assert run.confirm(cid, samples())['verdict'] == 'confirmed_gain'
    assert run.finalize(samples())['methods']['throughput']['median_ratio'] == pytest.approx(2)


def test_multiple_metrics_require_fixed_policy(tmp_path):
    from unittests.test_sequential_comparison import POLICY as SEQUENTIAL
    with pytest.raises(ValueError, match='multiple client metrics'):
        RunController.create(tmp_path/'run', _SYNTH, {'agent_profile': {'validation': VALIDATION}},
                             comparison_policy=SEQUENTIAL, eval_call_limit=300, final_eval_reserve=64)
    assert not (tmp_path/'run').exists()


def test_history_reproduces_all_client_metrics_and_rejects_tampered_secondary(ready):
    from agent import history
    run, cid = ready
    confirmed = run.confirm(cid, paired())
    snapshot = run.status()
    history._comparison(snapshot['manifest'], snapshot['state'], confirmed)
    corrupted = copy.deepcopy(confirmed)
    corrupted['methods']['tail']['candidate_median'] = 999
    with pytest.raises(ValueError, match='client metric confirmation'):
        history._comparison(snapshot['manifest'], snapshot['state'], corrupted)


def test_web_result_preserves_method_units_and_scoped_verdict(ready):
    from webUI.results import run_result
    run, cid = ready
    run.confirm(cid, paired())
    run.finalize(paired(5, 40))
    row = run_result(run.directory, run.directory.parent, 'custom')
    assert row['status'] == 'original_retained'
    assert [(m['label'], m['unit'], m['baseline'], m['candidate'], m['verdict']) for m in row['metrics']] == [
        ('最终配对 · benchmark', 'us', 10, 5, 'confirmed_gain'),
        ('最终配对 · tail', 'us', 20, 40, 'regression')]
