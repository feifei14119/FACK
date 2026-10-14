"""Web presentation uses recorded identities and final evidence, without GPU work."""
import json
from pathlib import Path
import threading
from urllib.request import urlopen

import pytest

from agent.run import RunController
from tools.tune_run_report import snapshot_report
from unittests.test_paired_validation import POLICY, evaluator
from unittests.test_session import _SYNTH
from unittests.test_tuning_run import CONTRACT, FakeEvaluator, passed, prepare
from webUI import results, server


def create(repo):
    contract = dict(CONTRACT, client='aiter/hsa/gfx942', client_identity={
        'resources': {'original_co': {'path': '/old checkout/hsa/gfx942/my_kernel.co'}}})
    return RunController.create(repo/'client/aiter/tune_out/runs/run-1', _SYNTH, contract,
                                perf_repeats=1, eval_call_limit=100,
                                final_eval_reserve=16, comparison_policy=POLICY)


def screen(run):
    run.evaluate('original', FakeEvaluator(passed(100)))
    candidate = prepare(run)['candidate_id']
    run.evaluate(candidate, FakeEvaluator(passed(1000)))
    return candidate


def row(repo):
    data = results.read_results(repo, ['aiter'])
    assert not data['errors']
    assert len(data['results']) == 1
    return data['results'][0]


@pytest.mark.parametrize('final_score,status,selected', [
    (110, 'final_recommended', 'candidate'), (99, 'original_retained', 'original')])
def test_final_uses_fresh_pairs_not_highest_screen(tmp_path, final_score, status, selected):
    run = create(tmp_path)
    candidate = screen(run)
    run.confirm(candidate, evaluator())
    run.finalize(evaluator('final', candidate=final_score))
    before = (run.directory/'state.json').read_bytes()
    result = row(tmp_path)
    assert result['target'] == {'client': 'aiter/hsa/gfx942', 'gfx': 'gfx942',
                               'co': '/old checkout/hsa/gfx942/my_kernel.co', 'symbol': None}
    assert result['status'] == status
    assert result['selected'] == (candidate if selected == 'candidate' else 'original')
    assert result['metrics'][0]['baseline'] == 100
    assert result['metrics'][0]['candidate'] == final_score
    assert result['metrics'][0]['unit'] == 'TFLOPS'
    assert result['metrics'][0]['gain_pct'] == pytest.approx(final_score-100)
    assert result['screening']['best'] == 1000
    assert (run.directory/'state.json').read_bytes() == before
    assert not (run.directory/'report').exists()


def test_current_state_wins_over_stale_report_and_read_does_not_export(tmp_path):
    run = create(tmp_path)
    screen(run)
    (run.directory/'report').mkdir()
    report = run.directory/'report/report.json'
    report.write_text('{"final_result": {"status": "final_recommended"}}')
    before = report.read_bytes()
    result = row(tmp_path)
    assert result['status'] == 'not_finalized'
    assert result['metrics'] == [] and result['selected'] is None
    assert snapshot_report(run.directory)['recommendation'] is None
    assert report.read_bytes() == before
    assert not (run.directory/'report/selected.s').exists()


def test_untimed_fallback_has_no_invented_zero_gain(tmp_path):
    run = create(tmp_path)
    run.finalize(FakeEvaluator())
    result = row(tmp_path)
    assert result['status'] == 'original_retained'
    assert result['selected'] == 'original'
    assert result['metrics'] == []


def test_corrupt_archive_withholds_winner(tmp_path):
    run = create(tmp_path)
    candidate = screen(run)
    run.confirm(candidate, evaluator())
    run.finalize(evaluator('final'))
    state = run.status()['state']
    (run.directory/state['candidates'][candidate]['artifact']['path']).write_text('corrupt')
    result = row(tmp_path)
    assert result['status'] == 'invalid'
    assert result['selected'] is None and result['metrics'] == []


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_comparison_separates_metrics_and_never_promotes_failed_data(tmp_path):
    p = tmp_path/'client/aiter/tune_out/comparisons/paired-x/comparison.json'
    data = {'client': 'aiter/hsa/gfx942', 'status': 'completed', 'results': {
        'hip_graph': {'reference_median_us': 10, 'candidate_median_us': 12, 'verdict': 'regression'},
        'op_test:uniform/auto': {'reference_median_us': 10, 'candidate_median_us': 8, 'verdict': 'confirmed_gain'}}}
    write(p, data)
    result = row(tmp_path)
    assert len(result['metrics']) == 2
    assert result['status'] == 'comparison_only' and result['selected'] is None
    assert result['metrics'][0]['verdict'] == 'regression'
    assert result['metrics'][1]['verdict'] == 'confirmed_gain'
    data['status'] = 'failed'
    write(p, data)
    assert row(tmp_path)['metrics'] == []


def test_legacy_missing_metadata_and_bad_files_are_explicit(tmp_path):
    root = tmp_path/'client/aiter/tune_out/tune_result'
    write(root/'legacy.summary.json', {'best': {'tflops': 999}})
    write(root/'broken.summary.json', [])
    write(root/'nan.summary.json', {'best': {'tflops': float('nan')}})
    data = results.read_results(tmp_path, ['aiter'])
    assert len(data['results']) == 1 and len(data['errors']) == 2
    result = data['results'][0]
    assert result['target']['co'] is None and result['target']['gfx'] is None
    assert result['status'] == 'screening_only' and result['metrics'] == []


def test_outside_symlink_is_not_followed(tmp_path):
    outside = tmp_path/'outside.json'
    outside.write_text('{}')
    repo = tmp_path/'repo'
    root = repo/'client/aiter/tune_out/comparisons/pair'
    root.mkdir(parents=True)
    (root/'comparison.json').symlink_to(outside)
    data = results.read_results(repo, ['aiter'])
    assert not data['results'] and len(data['errors']) == 1


def test_http_returns_archived_target_and_separate_timings():
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen('http://127.0.0.1:%d/api/results' % httpd.server_port) as response:
            data = json.load(response)
        assert not data['errors']
        records = {r['title']: r for r in data['results'] if r['kind'] == 'archive'}
        assert records['20261014']['status'] == 'original_retained'
        assert records['20261014-portability']['status'] == 'self_comparison'
        for r in records.values():
            assert r['target']['co'].endswith('32x128.co')
            assert r['target']['client'] == 'aiter/hsa/gfx942'
            assert len(r['metrics']) == 3
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
