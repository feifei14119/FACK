import csv
import json

from tools import aiter_campaign_monitor as monitor
from tools import campaign_workloads as workloads
from webUI.campaigns import read_campaigns


def plan():
    refs = [{'workload_id': key, 'family': 'a8w8', 'source': {'path': 'exact.csv', 'sha256': 'abc'},
             'line': line, 'effective_row': {'M': str(m), 'N': '1280', 'K': '1024', 'us': 'old'},
             'status': 'ready_for_validation', 'reason': 'awaiting runtime', 'matches': [{'co': 'same.co'}]}
            for key, line, m in [('task-a', 5, 192), ('task-b', 6, 384)]]
    return {'cu_num': 80, 'references': refs,
            'tasks': [{'task_id': r['workload_id'], 'co': 'same.co', 'inputs': {'m': int(r['effective_row']['M']), 'n': 1280, 'k': 1024}}
                      for r in refs], 'co_to_workloads': {'same.co': ['task-a', 'task-b']},
            'unreferenced_co': [{'co': 'unused.co', 'reason': 'no selected CSV reference'}]}


def control(tmp_path):
    return {'campaign_id': 'dispatch-test', 'started_at': '2026-10-15T00:55:41+00:00',
            'stop_condition': 'first_confirmed_winner', 'remote': 'example',
            'remote_output': '/fresh', 'local_output': str(tmp_path)}


def test_same_co_different_csv_dimensions_remain_independent(tmp_path):
    progress = {'kernels': [{'task_id': 'task-a', 'co': 'same.co', 'status': 'completed',
                            'metrics': {'campaign_decision': 'original_retained'}}]}
    snapshot = monitor.build_snapshot(control(tmp_path), {'plan.json': plan(), 'progress.json': progress},
                                      {'attempted_at': monitor.utcnow(), 'last_success_at': None, 'connected': True, 'errors': {}})
    assert snapshot['counts']['known'] == 2 and snapshot['counts']['finished'] == 1
    assert [r['task_id'] for r in snapshot['remaining']] == ['task-b']
    assert {r['workload']['inputs']['m'] for r in snapshot['kernels']} == {192, 384}
    assert [r['workload_id'] for r in snapshot['remaining_workloads']] == ['task-b']
    assert snapshot['co_coverage'][0]['remaining_workload_ids'] == ['task-b']
    assert snapshot['co_coverage'][1]['reason'] == 'no selected CSV reference'
    monitor.write_report(control(tmp_path), snapshot, final=True)
    rows = list(csv.DictReader((tmp_path / 'remaining.csv').open()))
    assert rows[0]['workload_id'] == 'task-b' and rows[0]['m'] == '384' and rows[0]['csv_row'] == '6'
    assert snapshot['deadline'] is None


def test_flat_remote_workload_preserves_csv_provenance(tmp_path):
    progress = {'kernels': [{'task_id': 'task-a', 'co': 'same.co', 'workload': {'m': 192, 'n': 1280, 'k': 1024,
        'csv_file': 'exact.csv', 'csv_row': 5}, 'status': 'baseline_validated'}]}
    snapshot = monitor.build_snapshot(control(tmp_path), {'plan.json': plan(), 'progress.json': progress},
                                      {'attempted_at': monitor.utcnow()})
    row = next(r for r in snapshot['kernels'] if r['task_id'] == 'task-a')
    assert row['workload']['inputs']['m'] == 192
    assert row['workload']['csv'] == [{'path': 'exact.csv', 'line': 5}]
    assert 'us' not in snapshot['workload_references'][0]['workload']['inputs']


def test_stop_requires_fresh_campaign_winner_identity(tmp_path):
    cfg = control(tmp_path)
    assert not monitor.success_requested(cfg, {'status': 'winner_confirmed'})
    assert not monitor.success_requested(cfg, {'status': 'running', 'winner': {'task_id': 'task-a'}})
    assert monitor.success_requested(cfg, {'status': 'winner_confirmed', 'winner': {'task_id': 'task-a'}})


def test_api_discovers_dispatch_directory_without_campaigns_parent(tmp_path):
    directory = tmp_path / 'client/aiter/tune_out/dispatch-test'
    directory.mkdir(parents=True)
    (directory / 'snapshot.json').write_text(json.dumps({'campaign_id': 'dispatch-test', 'kernels': []}))
    assert read_campaigns(tmp_path)['campaigns'][0]['campaign_id'] == 'dispatch-test'


def test_winner_current_alias_and_reserved_run_do_not_corrupt_counts(tmp_path):
    progress = {'current': 'task-a', 'kernels': [
        {'task_id': 'task-a', 'co': 'same.co', 'status': 'winner_confirmed',
         'metrics': {'valid_for_adoption': True, 'campaign_decision': 'winner_confirmed'}},
        {'task_id': 'task-b', 'co': 'same.co', 'status': 'pending', 'run_id': 'reserved',
         'reason': 'queued', 'metrics': {}}]}
    snapshot = monitor.build_snapshot(control(tmp_path), {'plan.json': plan(), 'progress.json': progress},
                                      {'attempted_at': monitor.utcnow()})
    assert snapshot['counts']['finished'] == 1
    assert snapshot['current_task_id'] == 'task-a' and snapshot['current_co'] == 'same.co'
    groups = monitor.progress_breakdown(snapshot)
    assert [r['task_id'] for r in groups['not_started']] == ['task-b']
    assert len(groups['completed_candidate_adopted']) == 1
    assert '已采用 **1**' in '\n'.join(monitor.outcome_summary(snapshot))


def test_metric_summary_best_correct_screen_is_not_confirmed_gain():
    summary = monitor.metric_summary({'candidate_screens': [
        {'candidate_id': 'wrong', 'correct': False, 'hip_graph': {'median_us': 1}},
        {'candidate_id': 'zero', 'correct': True, 'hip_graph': {'median_us': 0}},
        {'candidate_id': 'invalid', 'correct': True, 'hip_graph': {'median_us': None}},
        {'candidate_id': 'slower', 'correct': True, 'hip_graph': {'median_us': 7}},
        {'candidate_id': 'best', 'correct': True, 'valid_samples': 3,
         'hip_graph': {'median_us': 6.2}, 'op_test': {'median_us': 6.8}}],
        'paired_results': [{'stage': 'final', 'gain_pct': 99}]})
    assert 'screening（未独立确认）' in summary
    assert '正确候选 best，HIP graph 6.20000 us，op_test 6.8 us，有效样本 3' in summary
    assert '筛选值不代表已确认收益' in summary
    assert all(word not in summary for word in ['wrong', 'slower', 'gain='])


def test_multiple_optest_distributions_are_aggregate_screen_only():
    methods = ['hip_graph', 'op_test:constant/constant', 'op_test:uniform/auto']
    metrics = {'original_screen': {'measurement': {'samples': [{'result': {'correct': True, 'time_us': 6,
        'detail': {'runner': {'op_test': {'rows': [
            {'data_init': 'constant', 'scale_init': 'constant', 'asm us': 7},
            {'data_init': 'uniform', 'scale_init': 'auto', 'asm us': 8}]}}}}}]}},
        'paired_results': [{'method': method, 'stage': 'final', 'scope': 'independent_paired'} for method in methods]}
    summary = monitor.metric_summary(metrics)
    assert 'op_test（多分布 aggregate screen） 7.00000–8.00000 us' in summary
    for method in methods:
        assert 'final %s：' % method in summary


def test_explicit_moe_and_mla_tasks_keep_source_and_category_without_inventing_csv(tmp_path):
    explicit = {'cu_num': 80, 'references': [], 'tasks': [
        {'task_id': 'moe-one', 'co': 'moe.co', 'category': 'moe',
         'source_kind': 'reviewed_explicit_non_csv', 'inputs': {'family': 'fp8', 'm': 1024, 'experts': 4}},
        {'task_id': 'mla-one', 'co': 'mla.co', 'category': 'mla',
         'source_kind': 'reviewed_explicit_non_csv', 'inputs': {'family': 'bf16', 'batch_size': 8, 'kv_len': 1024}}]}
    planned = workloads.plan_tasks(explicit)
    assert [row['category'] for row in planned] == ['moe', 'mla']
    assert all(row['workload']['csv'] == [] for row in planned)
    assert all(row['workload']['selection'] == 'reviewed_explicit_non_csv' for row in planned)
    progress = {'kernels': [{'task_id': task['task_id'], 'co': task['co'], 'workload': {
        'id': task['task_id'], 'inputs': task['inputs'], 'csv': [], 'selection': task['source_kind']}}
        for task in explicit['tasks']]}
    snapshot = monitor.build_snapshot(control(tmp_path), {'plan.json': explicit, 'progress.json': progress},
                                      {'attempted_at': monitor.utcnow()})
    assert {row['category'] for row in snapshot['kernels']} == {'moe', 'mla'}
    assert all(row['workload']['csv'] == [] for row in snapshot['kernels'])
    assert all(row['workload']['selection'] == 'reviewed_explicit_non_csv' for row in snapshot['kernels'])
    assert snapshot['coverage_counts']['csv_references'] == 0
    assert snapshot['counts']['target_count'] == snapshot['counts']['remaining'] == 2
    assert all(workloads.csv_fields(row)['csv_file'] == workloads.csv_fields(row)['csv_row'] == ''
               for row in snapshot['kernels'])


def test_actual_csv_reference_is_recovered_for_sparse_progress_workload(tmp_path):
    progress = {'kernels': [{'task_id': 'task-a', 'co': 'same.co',
        'workload': {'id': 'task-a', 'inputs': {'m': 192, 'n': 1280, 'k': 1024}, 'csv': []}}]}
    snapshot = monitor.build_snapshot(control(tmp_path), {'plan.json': plan(), 'progress.json': progress},
                                      {'attempted_at': monitor.utcnow()})
    row = next(row for row in snapshot['kernels'] if row['task_id'] == 'task-a')
    assert row['workload']['csv'] == [{'path': 'exact.csv', 'sha256': 'abc', 'line': 5}]
