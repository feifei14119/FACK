"""Campaign monitoring tests use synthetic files; no remote or GPU work."""
import json
from pathlib import Path
import subprocess
import sys

from tools import aiter_campaign_monitor as monitor
from webUI.campaigns import read_campaigns


def config(tmp_path):
    return {'campaign_id': 'test', 'started_at': '2026-10-14T11:52:27Z',
            'deadline': '2026-10-14T21:52:27Z', 'remote': 'example',
            'remote_output': '/task/output', 'local_output': str(tmp_path)}


def test_failed_sync_preserves_last_success_and_marks_disconnected(tmp_path):
    control = config(tmp_path)
    def good(_):
        return {'files': {'progress.json': {'campaign_id': 'test', 'status': 'running',
                'kernels': [{'co': 'a.co', 'status': 'screening', 'metrics': {'us': 2}}]}}, 'errors': {}}
    first = monitor.sync_once(control, fetcher=good)
    def failed(_):
        raise subprocess.TimeoutExpired('ssh', 45)
    second = monitor.sync_once(control, fetcher=failed)
    assert second['sync']['connected'] is False
    assert second['sync']['last_success_at'] == first['sync']['last_success_at']
    assert second['kernels'] == first['kernels']
    assert 'communication' in second['sync']['errors']
    assert '最后同步记录' in monitor.markdown_report(second)


def test_counts_require_measured_completion_and_separate_scope(tmp_path):
    docs = {'inventory.json': {'kernels': [{'co': 'other.co', 'status': 'out_of_scope'},
            {'co': 'missing.co'}, {'co': 'blocked.co', 'status': 'blocked'}]},
            'remaining.json': {'kernels': [{'co': 'done.co', 'status': 'pending'}]},
            'progress.json': {'kernels': [{'co': 'done.co', 'status': 'original_retained', 'metrics': {'us': 1}},
             {'co': 'untimed.co', 'status': 'original_retained', 'metrics': {}}]}}
    snapshot = monitor.build_snapshot(config(tmp_path), docs, {'attempted_at': monitor.utcnow()})
    assert snapshot['counts']['known'] == 5
    assert snapshot['counts']['target_count'] == 4
    assert snapshot['counts']['out_of_scope'] == 1
    assert snapshot['counts']['finished'] == 1
    assert {row['co'] for row in snapshot['remaining']} == {'missing.co', 'blocked.co', 'untimed.co'}
    assert next(row for row in snapshot['kernels'] if row['co'] == 'done.co')['status'] == 'original_retained'


def test_final_report_csv_includes_all_unfinished_targets(tmp_path):
    control = config(tmp_path)
    snapshot = monitor.sync_once(control, final=True, fetcher=lambda _: {'files': {
        'inventory.json': {'kernels': [{'co': 'pending.co', 'category': 'gemm', 'reason': 'deadline'}]}}, 'errors': {}})
    monitor.write_report(control, snapshot, final=True)
    assert snapshot['monitor_status'] == 'finished'
    assert 'pending.co' in (tmp_path / 'remaining.csv').read_text()
    assert (tmp_path / 'final-report.md').exists()
    assert json.loads((tmp_path / 'reports.jsonl').read_text())['final'] is True


def test_web_reader_only_reads_explicit_local_campaign_snapshots(tmp_path):
    root = tmp_path / 'client/aiter/tune_out/campaigns/test'
    root.mkdir(parents=True)
    monitor.atomic_json(root / 'snapshot.json', {'campaign_id': 'test', 'kernels': []})
    other = tmp_path / 'outside.json'
    other.write_text('{}')
    bad = tmp_path / 'client/aiter/tune_out/campaigns/bad'
    bad.mkdir()
    (bad / 'snapshot.json').symlink_to('/dev/null')
    data = read_campaigns(tmp_path)
    assert len(data['campaigns']) == 1
    assert len(data['errors']) == 1


def test_final_monitor_status_does_not_imply_gpu_stopped(tmp_path):
    control = config(tmp_path)
    unknown = monitor.sync_once(control, final=True, fetcher=lambda _: {'files': {}, 'errors': {}})
    assert unknown['monitor_status'] == 'finished'
    assert unknown['gpu_stop']['status'] == 'stop_unverified'
    stopped = monitor.sync_once(control, final=True, fetcher=lambda _: {
        'files': {}, 'errors': {}, 'container_state': {'Running': False, 'Status': 'exited'}})
    assert stopped['gpu_stop']['status'] == 'stopped'
    running = monitor.sync_once(control, final=True, fetcher=lambda _: {
        'files': {}, 'errors': {}, 'container_state': {'Running': True}})
    assert running['gpu_stop']['status'] == 'still_running'
    watchdog = monitor.sync_once(control, final=True, fetcher=lambda _: {
        'files': {'watchdog-stop.json': {'returncode': 0}}, 'errors': {}})
    assert watchdog['gpu_stop']['status'] == 'stopped'


def test_sync_crossing_deadline_requires_new_post_deadline_read(tmp_path, monkeypatch):
    control = config(tmp_path)
    control_path = tmp_path / 'control.json'
    control_path.write_text(json.dumps(control))
    deadline = monitor.timestamp(control['deadline'])
    now = [deadline - 1]
    calls, reports = [], []
    def sync(_control, final=False):
        calls.append((now[0], final))
        now[0] += 2
        return monitor.build_snapshot(_control, {}, {'attempted_at':monitor.utcnow(),
            'connected':True,'last_success_at':monitor.utcnow(),'errors':{}}, final=final)
    monkeypatch.setattr(monitor.time, 'time', lambda: now[0])
    monkeypatch.setattr(monitor.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(monitor, 'sync_once', sync)
    monkeypatch.setattr(monitor, 'write_report', lambda *args, **kwargs: reports.append(kwargs))
    monkeypatch.setattr(monitor, 'sync_exports', lambda *args: {'status': 'no_confirmed_exports'})
    monkeypatch.setattr(sys, 'argv', ['monitor', '--control', str(control_path)])
    monitor.main()
    assert calls == [(deadline - 1, False), (deadline + 5, True)]
    assert reports == [{'final': True}]


def test_posthoc_failure_is_unfinished_and_cannot_be_read_as_a_gain(tmp_path):
    control = config(tmp_path)
    snapshot = monitor.sync_once(control, fetcher=lambda _: {'files': {'progress.json': {'kernels': [
        {'co': 'invalid.co', 'status': 'completed', 'metrics': {'valid_for_adoption': False, 'gain_pct': 4}}]}}, 'errors': {}})
    assert snapshot['counts']['finished'] == 0
    assert snapshot['remaining'][0]['co'] == 'invalid.co'
    assert '候选验证失败，不可采用；历史配对值不计有效收益' in monitor.markdown_report(snapshot)


def test_normal_original_retained_with_null_adoption_flag_remains_complete(tmp_path):
    snapshot = monitor.sync_once(config(tmp_path), fetcher=lambda _: {'files': {'progress.json': {'kernels': [
        {'co': 'retained.co', 'status': 'completed', 'metrics': {'valid_for_adoption': None,
          'original_screen': {'status': 'measured', 'time_us': 10}, 'final': {'status': 'original_retained'}}}]}}, 'errors': {}})
    assert snapshot['counts']['finished'] == 1
    assert snapshot['remaining'] == []


def test_report_crossing_slot_uses_slot_filename_and_retains_real_snapshot_time(tmp_path):
    control=config(tmp_path)
    snapshot=monitor.sync_once(control, fetcher=lambda _: {'files':{},'errors':{}})
    snapshot['generated_at']='2026-10-14T14:12:20Z'
    snapshot['scheduled_report_at']='2026-10-14T14:12:27Z'
    monitor.write_report(control,snapshot)
    report=tmp_path/'report-20261014T141227Z.json'
    assert report.exists()
    saved=json.loads(report.read_text())
    assert saved['generated_at']=='2026-10-14T14:12:20Z'
    assert saved['scheduled_report_at']=='2026-10-14T14:12:27Z'


def test_outcome_summary_uses_final_original_pairs_and_verified_local_links(tmp_path):
    rows=[{'co':'a.co','status':'completed','metrics':{'valid_for_adoption':True,
            'campaign_decision':'final_recommended','paired_results':[
                {'stage':'confirm','reference_id':'cand_old','scope':'independent_paired','gain_pct':99},
                {'stage':'final','reference_id':'original','scope':'independent_paired','method':'hip_graph',
                 'reference_median_us':100,'candidate_median_us':50,'gain_pct':7,'pairs':8,'verdict':'confirmed_gain'}]}},
          {'co':'retained.co','status':'completed','metrics':{'final':{'status':'original_retained'}}},
          {'co':'bad.co','status':'blocked','metrics':{'valid_for_adoption':False,'campaign_decision':'final_recommended'}},
          {'co':'unknown.co','status':'coverage_pending'}, {'co':'pending.co','status':'pending'}]
    snapshot=monitor.sync_once(config(tmp_path),fetcher=lambda _: {'files':{'progress.json':{'kernels':rows}},'errors':{}})
    destination=tmp_path/'exports/run/selected.co';destination.parent.mkdir(parents=True);destination.write_bytes(b'abc')
    snapshot['local_exports']={'status':'verified','files':[{'co':'a.co','path':'run/selected.co','verified':True,'size_bytes':3}]}
    summary='\n'.join(monitor.outcome_summary(snapshot))
    assert '已采用 **1**；保留原始 **1**；阻塞 **1**' in summary
    assert '+7.00000%' in summary and '99%' not in summary and '100%' not in summary
    assert '[selected.co](exports/run/selected.co)' in summary


def test_final_breakdown_distinguishes_unstarted_failures_coverage_and_retained(tmp_path):
    rows=[{'co':'never.co','status':'pending','run_id':None},
          {'co':'seed.co','status':'blocked','run_id':None,'reason':'original validation failed: adapter error'},
          {'co':'candidate.co','status':'blocked','run_id':'run-1','reason':'no_valid_candidate'},
          {'co':'coverage.co','status':'coverage_pending','run_id':'run-2'},
          {'co':'unclear.co','status':'blocked','reason':'unclassified error'},
          {'co':'retained.co','status':'completed','run_id':'run-3','metrics':{'final':{'status':'original_retained'}}}]
    control=config(tmp_path)
    snapshot=monitor.sync_once(control,final=True,fetcher=lambda _: {'files':{'progress.json':{'kernels':rows}},'errors':{}})
    groups=monitor.progress_breakdown(snapshot)
    assert [r['co'] for r in groups['not_started']]==['never.co']
    assert [r['co'] for r in groups['seed_or_adapter_failed']]==['seed.co']
    assert [r['co'] for r in groups['candidate_or_retest_incomplete']]==['candidate.co']
    assert [r['co'] for r in groups['coverage_pending']]==['coverage.co']
    assert [r['co'] for r in groups['unresolved_stage']]==['unclear.co']
    assert [r['co'] for r in groups['completed_original_retained']]==['retained.co']
    monitor.write_report(control,snapshot,final=True)
    assert 'seed_or_adapter_failed,seed.co' in (tmp_path/'remaining-by-stage.csv').read_text()
    assert 'retained.co' not in (tmp_path/'remaining.csv').read_text()
    assert 'retained.co' in (tmp_path/'completed-original-retained.csv').read_text()
    assert snapshot['kernels'][0]['status']=='blocked'  # sorted candidate.co remains authoritative


def test_not_started_evidence_overrides_preassigned_run_id(tmp_path):
    rows = [
        {'co': 'stage.co', 'status': 'blocked', 'run_id': 'planned-1',
         'result_stage': 'not_started', 'reason': 'phase budget exhausted'},
        {'co': 'reason.co', 'status': 'blocked', 'run_id': 'planned-2',
         'reason': 'not_started_before_gemm_phase_transition: time reserved for migration'},
        {'co': 'attempted.co', 'status': 'blocked', 'run_id': 'attempted-1',
         'result_stage': 'candidate', 'reason': 'candidate retest incomplete'},
    ]
    snapshot = monitor.sync_once(config(tmp_path), fetcher=lambda _: {
        'files': {'progress.json': {'kernels': rows}}, 'errors': {}})
    groups = monitor.progress_breakdown(snapshot)
    assert {row['co'] for row in groups['not_started']} == {'stage.co', 'reason.co'}
    assert [row['co'] for row in groups['candidate_or_retest_incomplete']] == ['attempted.co']
    assert all(row['status'] == 'blocked' for row in snapshot['kernels'])


def test_independent_diagnostic_preserved_without_changing_completion(tmp_path):
    diagnostic = {'id': 'moe-control', 'status': 'running', 'scope': 'diagnostic_only',
                  'records_completed': 3, 'directory': '/remote/diagnostic', 'summary_path': None}
    snapshot = monitor.sync_once(config(tmp_path), fetcher=lambda _: {
        'files': {'progress.json': {'phase': 'moe', 'status': 'running',
            'active_step': 'diagnostic_control_compare', 'diagnostic': diagnostic,
            'diagnostic_history': [{'id': 'previous-control', 'no_adoption': True}],
            'kernels': [{'co': 'moe.co', 'status': 'coverage_pending'}]}}, 'errors': {}})
    assert snapshot['diagnostic'] == diagnostic
    assert snapshot['diagnostic_history'] == [{'id': 'previous-control', 'no_adoption': True}]
    assert snapshot['counts']['finished'] == 0
    assert snapshot['counts']['by_status'] == {'coverage_pending': 1}
    report = monitor.markdown_report(snapshot)
    assert '独立诊断不计入候选采用或 .co 完成数' in report
    assert 'moe-control' in report and '"records_completed": 3' in report
    assert 'previous-control' in report and '历史独立诊断' in report


def test_full_campaign_closes_only_after_attempts_and_associations_without_counting_failures(tmp_path):
    control = dict(config(tmp_path), deadline=None, stop_condition='all_runnable_workloads_completed')
    progress = {'status': 'completed', 'completion': {'all_tasks_attempted': True,
        'associations_finished': True, 'total_tasks': 2, 'attempted_tasks': 2}, 'kernels': [
        {'task_id': 'ok', 'co': 'a.co', 'status': 'completed', 'attempt_finished_at': monitor.utcnow(),
         'metrics': {'campaign_decision': 'original_retained'}},
        {'task_id': 'bad', 'co': 'b.co', 'status': 'blocked', 'attempt_finished_at': monitor.utcnow()}]}
    documents = {'plan.json': {'tasks': [{'task_id': 'ok', 'co': 'a.co'}, {'task_id': 'bad', 'co': 'b.co'}],
        'references': [{'workload_id': 'unsupported', 'status': 'unsupported_adapter', 'matches': []}]},
        'progress.json': progress}
    snapshot = monitor.build_snapshot(control, documents, {'attempted_at': monitor.utcnow(),
        'connected': True, 'last_success_at': monitor.utcnow(), 'errors': {}})
    assert monitor.success_requested(control, snapshot)
    assert snapshot['counts']['finished'] == 1
    assert snapshot['remaining'][0]['task_id'] == 'bad'
    assert snapshot['remaining_workloads'][0]['workload_id'] == 'unsupported'
    report = monitor.markdown_report(snapshot)
    assert '全部可调优任务完成' in report and '已尝试不等于通过完成验收' in report
    assert '首个严格确认胜出' not in report
    snapshot['status'] = 'all_runnable_workloads_attempted'
    assert not monitor.success_requested(control, snapshot)
    snapshot['status'] = 'completed'
    for field in ('all_tasks_attempted', 'associations_finished'):
        snapshot['completion'][field] = False
        assert not monitor.success_requested(control, snapshot)
        snapshot['completion'][field] = True
    snapshot['completion']['attempted_tasks'] = 1
    assert not monitor.success_requested(control, snapshot)
    snapshot['completion']['attempted_tasks'] = 2
    snapshot['sync']['connected'] = False
    assert not monitor.success_requested(control, snapshot)
    snapshot['sync']['connected'] = True
    snapshot['sync']['errors']['progress.json'] = 'missing'
    assert not monitor.success_requested(control, snapshot)
    snapshot['sync']['errors'] = {}
    snapshot['kernels'][1]['status'] = 'pending'
    assert not monitor.success_requested(control, snapshot)


def test_full_campaign_waits_for_fresh_container_stop_before_finalizing(tmp_path, monkeypatch):
    control = dict(config(tmp_path), deadline=None, stop_condition='all_runnable_workloads_completed')
    control_path = tmp_path / 'control.json'
    control_path.write_text(json.dumps(control))
    documents = {'plan.json': {'tasks': [{'task_id': 'one', 'co': 'a.co'}]},
        'progress.json': {'status': 'completed', 'completion': {'all_tasks_attempted': True,
            'associations_finished': True, 'total_tasks': 1, 'attempted_tasks': 1},
            'kernels': [{'task_id': 'one', 'co': 'a.co', 'status': 'completed',
                'attempt_finished_at': monitor.utcnow(), 'metrics': {'campaign_decision': 'original_retained'}}]}}
    calls, finalized = [], []
    def sync(_control, final=False):
        calls.append(final)
        snapshot = monitor.build_snapshot(_control, documents, {'attempted_at': monitor.utcnow(),
            'connected': True, 'last_success_at': monitor.utcnow(), 'errors': {}}, final=final)
        snapshot['gpu_stop'] = {'container_state': {'Running': len(calls) < 4}}
        return snapshot
    monkeypatch.setattr(monitor, 'sync_once', sync)
    monkeypatch.setattr(monitor, 'write_report', lambda *args, **kwargs: None)
    monkeypatch.setattr(monitor, 'finalize', lambda _control, snapshot: finalized.append(snapshot))
    monkeypatch.setattr(monitor.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(sys, 'argv', ['monitor', '--control', str(control_path)])
    monitor.main()
    assert calls == [False, True, False, True]
    assert len(finalized) == 1 and finalized[0]['gpu_stop']['container_state']['Running'] is False


def test_unspecified_unlimited_monitor_does_not_imply_first_winner():
    assert '未声明' in monitor.stop_condition_label({'deadline': None})
    assert '首个' not in monitor.stop_condition_label({'deadline': None})


def test_adapter_coverage_reasons_are_exported_without_changing_workload_completion(tmp_path):
    import csv
    control = config(tmp_path)
    reasons = {'a.co': 'other contracts remain unadapted', 'b.co': 'unsupported, keep original reason'}
    snapshot = monitor.sync_once(control, fetcher=lambda _: {'files': {
        'plan.json': {'tasks': [{'task_id': 'one', 'co': 'a.co'}], 'adapter_blocked_reasons': reasons},
        'progress.json': {'kernels': [{'task_id': 'one', 'co': 'a.co', 'status': 'completed',
                                      'metrics': {'campaign_decision': 'original_retained'}}]}}, 'errors': {}})
    monitor.write_report(control, snapshot)
    assert snapshot['adapter_coverage']['reasons'] == reasons
    assert snapshot['counts']['finished'] == snapshot['counts']['target_count'] == 1
    assert snapshot['remaining'] == []
    rows = list(csv.DictReader((tmp_path / 'adapter-coverage-reasons.csv').open()))
    assert {row['co']: row['reason'] for row in rows} == reasons
    assert {row['source'] for row in rows} == {'plan.json:adapter_blocked_reasons'}
    report = monitor.markdown_report(snapshot)
    assert '部分对象另有显式可运行任务' in report and '不表示全部未调优' in report


def test_local_publication_summary_reads_only_matching_receipts(tmp_path):
    path = tmp_path / 'manager-status.json'
    state = {'campaign_id': 'test', 'status': 'watching', 'receipts': {
        'one': {'status': 'published', 'commit': 'first', 'checked_at': '2026-10-16T00:00:00Z'},
        'two': {'status': 'published', 'commit': 'second', 'checked_at': '2026-10-16T00:01:00Z'},
        'three': {'status': 'skipped'}}, 'errors': {'four': {'error': 'verification failed'}}}
    original = json.dumps(state)
    path.write_text(original)
    summary = monitor.publication_summary(tmp_path, 'test')
    assert summary['published'] == 2 and summary['skipped'] == 1 and summary['error_count'] == 1
    assert summary['latest_commit'] == 'second'
    assert path.read_text() == original
    assert monitor.publication_summary(tmp_path, 'other')['status'] == 'read_failed'
