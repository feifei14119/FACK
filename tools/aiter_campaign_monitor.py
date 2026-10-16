#!/usr/bin/env python3
"""Read three campaign JSON files over SSH; persist local progress and reports.

This process never starts GPU work, follows artifact paths, or scans a checkout.
Run from the repository root with --control <campaign/control.json>.
"""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import io
import html
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import time
from urllib.parse import quote

if __package__:
    from .aiter_campaign_exports import sync_exports
    from .aiter_campaign_diagnostics import sync_diagnostic
    from . import campaign_workloads as workloads
else:
    from aiter_campaign_exports import sync_exports
    from aiter_campaign_diagnostics import sync_diagnostic
    import campaign_workloads as workloads

FILES = ('inventory.json', 'plan.json', 'progress.json', 'remaining.json')
OPTIONAL_FILES = ('watchdog.json', 'watchdog-stop.json')
FINISHED = {'completed', 'done', 'optimized', 'confirmed_gain',
            'final_recommended', 'original_retained', 'retained_original', 'winner_confirmed'}
LIMIT = 32 * 1024 * 1024
STAGE_LABELS = {
    'not_started': '未开始',
    'seed_or_adapter_failed': 'seed / 适配失败',
    'candidate_or_retest_incomplete': '候选 / 复测未完成',
    'coverage_pending': '模型覆盖待核实',
    'unresolved_stage': '阶段证据不足，需核对',
    'completed_original_retained': '已完成，保留原始代码',
    'completed_candidate_adopted': '已完成，采用候选',
    'completed_other': '已完成，其他记录状态',
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(str(temp), str(path))


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def entries(value):
    if isinstance(value, dict):
        for name in ('kernels', 'tasks', 'code_objects', 'objects', 'items', 'remaining'):
            if name in value:
                return entries(value[name])
        return []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            item = {'co': item}
        if isinstance(item, dict):
            item = dict(item)
            item['co'] = item.get('co') or item.get('path') or item.get('name')
            if item['co']:
                result.append(item)
    return result


def in_scope(row):
    return row.get('in_scope') is not False and row.get('status') != 'out_of_scope' and str(
        row.get('category', '')).lower() not in ('fmha', 'pa', 'allreduce', 'other', 'out_of_scope')


def progress_breakdown(snapshot):
    """Classify final work coverage without changing authoritative remote status."""
    unfinished = {workloads.key(row) for row in snapshot['remaining']}
    groups = {name: [] for name in STAGE_LABELS}
    for row in snapshot['kernels']:
        if not in_scope(row):
            continue
        status = str(row.get('status', '')).lower()
        reason = str(row.get('reason', '')).lower()
        stage = str(row.get('result_stage') or row.get('phase') or '').lower()
        metrics = row.get('metrics') or {}
        if not isinstance(metrics, dict):
            metrics = {}
        decision = metrics.get('campaign_decision') or (metrics.get('final') or {}).get('status')
        if workloads.key(row) not in unfinished:
            if decision in ('original_retained', 'retained_original'):
                group = 'completed_original_retained'
            elif metrics.get('valid_for_adoption') is True:
                group = 'completed_candidate_adopted'
            else:
                group = 'completed_other'
        elif status == 'coverage_pending' or 'static_model_coverage_pending' in reason:
            group = 'coverage_pending'
        elif (status in ('not_started', 'unstarted') or stage in ('not_started', 'unstarted') or
              reason == 'not_started' or reason.startswith(('not_started:', 'not_started_before_'))):
            group = 'not_started'
        elif status in ('pending', 'pending_original_validation', 'queued', 'discovered') and not metrics:
            group = 'not_started'
        elif status in ('blocked', 'failed', 'error', 'seed_failed', 'adapter_failed') and (
                stage in ('seed', 'prepare', 'adapter', 'environment', 'initializing') or
                any(marker in reason for marker in ('prepare:', 'original validation failed', 'seed validation failed',
                                                    'adapter failed', 'missing adapter', 'unsupported adapter',
                                                    'manifest not found', 'environment setup failed'))):
            group = 'seed_or_adapter_failed'
        elif row.get('run_id') or metrics or stage in ('candidate', 'screening', 'confirm', 'final'):
            group = 'candidate_or_retest_incomplete'
        elif not row.get('run_id') and status in ('pending', 'pending_original_validation', 'queued', 'discovered', ''):
            group = 'not_started'
        else:
            group = 'unresolved_stage'
        groups[group].append(row)
    return groups


def fetch_remote(control):
    # Every path is a fixed child of the explicitly configured campaign directory.
    script = '''import json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
data, errors = {}, {}
for name in json.loads(sys.argv[3]) + ["watchdog.json", "watchdog-stop.json"]:
    try:
        path = root / name
        if path.is_symlink():
            raise ValueError("symlink is not a campaign state file")
        if path.stat().st_size > 33554432:
            raise ValueError("state file exceeds 32 MiB")
        data[name] = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        if name not in ("watchdog.json", "watchdog-stop.json") or not isinstance(exc, FileNotFoundError):
            errors[name] = str(exc)
result = {"files": data, "errors": errors}
if len(sys.argv) > 2 and sys.argv[2]:
    try:
        proc = subprocess.run(["docker", "inspect", "--format", "{{json .State}}", sys.argv[2]],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-1000:])
        result["container_state"] = json.loads(proc.stdout)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        errors["container_inspect"] = str(exc)
print(json.dumps(result, allow_nan=False))
'''
    container = control.get('container', '') if control.get('_verify_stop') else ''
    state_files = control.get('state_files', ['inventory.json', 'progress.json', 'remaining.json'])
    if not isinstance(state_files, list) or any(name not in FILES for name in state_files):
        raise ValueError('invalid fixed state file list')
    remote_cmd = 'python3 -c %s %s %s %s' % (shlex.quote(script),
        shlex.quote(control['remote_output']), shlex.quote(container), shlex.quote(json.dumps(state_files)))
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
         '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
         control['remote'], remote_cmd], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=45, universal_newlines=True)
    if result.returncode:
        raise RuntimeError('SSH rc=%d: %s' % (result.returncode, result.stderr[-3000:].strip()))
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or not isinstance(value.get('files'), dict):
        raise ValueError('Invalid remote envelope')
    for name, data in list(value['files'].items()):
        if name not in FILES + OPTIONAL_FILES or not isinstance(data, (dict, list)):
            raise ValueError('Invalid campaign state: ' + name)
        if isinstance(data, dict) and data.get('campaign_id') not in (None, control['campaign_id']):
            raise ValueError('Campaign identity mismatch: ' + name)
    return value


def build_snapshot(control, documents, sync, previous=None, final=False):
    previous = previous or {}
    progress = documents.get('progress.json') or {}
    if not isinstance(progress, dict):
        progress = {'kernels': progress}
    plan = documents.get('plan.json') or {}
    planned = {workloads.key(row): row for row in workloads.plan_tasks(plan)}
    merged = {key: dict(row) for key, row in planned.items()}
    for name in ('inventory.json', 'remaining.json', 'progress.json'):
        for row in entries(documents.get(name)):
            identity = workloads.key(row)
            # Remaining lists often contain only identity and reason; do not
            # discard actual measurements already published in progress.
            merged.setdefault(identity, {'co': row['co'], 'status': 'pending'}).update(row)
    kernels = sorted(merged.values(), key=lambda row: (str(row.get('category', '')), row['co'], workloads.key(row)))
    for row in kernels:
        if row.get('task_id') or row.get('workload_id'):
            normalized = workloads.workload(row)
            prior = planned.get(workloads.key(row))
            if prior and not normalized.get('csv'):
                normalized['csv'] = prior['workload']['csv']
            row['workload'] = normalized
    current_id = progress.get('current_task_id') or progress.get('current')
    current_row = next((row for row in kernels if workloads.key(row) == current_id), {})
    targets = [row for row in kernels if in_scope(row)]
    remaining = [row for row in targets if row.get('status') not in FINISHED or not row.get('metrics')
                 or (isinstance(row.get('metrics'), dict) and row['metrics'].get('valid_for_adoption') is False)]
    counts = {}
    for row in kernels:
        state = str(row.get('status', 'pending'))
        counts[state] = counts.get(state, 0) + 1
    snapshot = {
        'schema_version': 1, 'campaign_id': control['campaign_id'],
        'started_at': control['started_at'], 'deadline': control.get('deadline'),
        'stop_condition': control.get('stop_condition', 'deadline'),
        'row_identity': 'workload' if plan or any(r.get('task_id') for r in kernels) else 'co',
        'phase_deadlines': control.get('phase_deadlines', {}),
        'generated_at': sync['attempted_at'], 'remote_updated_at': progress.get('updated_at'),
        'remote': control['remote'], 'remote_output': control['remote_output'],
        'remote_workspace': control.get('remote_workspace'),
        'container_workspace': '/workspace/FACK',
        'local_output': control['local_output'], 'sync': sync,
        'monitor_status': 'finished' if final else 'running',
        'status': progress.get('status', 'awaiting_remote_state'),
        'phase': progress.get('phase'), 'current_co': progress.get('current_co') or current_row.get('co'),
        'active_step': progress.get('active_step'),
        'current_task_id': current_id, 'winner': progress.get('winner'),
        'diagnostic': progress.get('diagnostic'),
        'diagnostic_history': progress.get('diagnostic_history', []),
        'category_counts': progress.get('category_counts', {}),
        'completion': progress.get('completion', {}),
        'planned_task_ids': list(planned),
        'counts': {'known': len(kernels), 'target_count': len(targets),
                   'out_of_scope': len(kernels) - len(targets),
                   'finished': len(targets) - len(remaining),
                   'remaining': len(remaining), 'by_status': counts},
        'remote_counts': progress.get('counts', {}),
        'kernels': kernels, 'remaining': remaining,
        'latest_report': previous.get('latest_report'),
        'notes': progress.get('notes', []),
        'gpu_stop': {'status': 'stop_unverified' if final else 'not_checked'},
    }
    if plan:
        snapshot.update(workloads.coverage(plan, kernels, remaining))
        reasons = plan.get('adapter_blocked_reasons')
        if isinstance(reasons, dict):
            snapshot['adapter_coverage'] = {'source': 'plan.json:adapter_blocked_reasons',
                'reasons': reasons, 'count': len(reasons)}
    return snapshot


def publication_summary(root, campaign_id):
    """Read only the supervisor's fixed local receipt index, never publish."""
    path = Path(root) / 'manager-status.json'
    if not path.exists():
        return {}
    try:
        if path.is_symlink() or path.stat().st_size > 1024 * 1024:
            raise ValueError('invalid local publication status path or size')
        state = json.loads(path.read_text())
        if state.get('campaign_id') != campaign_id:
            raise ValueError('local publication campaign identity mismatch')
        receipts = state.get('receipts') or {}
        errors = state.get('errors') or {}
        if not isinstance(receipts, dict) or not isinstance(errors, dict):
            raise ValueError('invalid local publication receipt index')
        published = [row for row in receipts.values() if isinstance(row, dict) and row.get('status') == 'published']
        latest = max(published, key=lambda row: row.get('checked_at', ''), default={})
        return {'source': str(path), 'status': state.get('status'), 'updated_at': state.get('updated_at'),
                'published': len(published), 'skipped': sum(isinstance(row, dict) and row.get('status') == 'skipped'
                                                         for row in receipts.values()),
                'error_count': len(errors), 'errors': errors, 'latest_commit': latest.get('commit'),
                'connection_error': state.get('connection_error')}
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        return {'source': str(path), 'status': 'read_failed', 'error': str(exc)}


def sync_once(control, final=False, fetcher=fetch_remote):
    root = Path(control['local_output'])
    previous = read_json(root / 'snapshot.json', {})
    prior_sync = previous.get('sync', {})
    sync = {'attempted_at': utcnow(), 'connected': False,
            'last_success_at': prior_sync.get('last_success_at'),
            'files': dict(prior_sync.get('files', {})), 'errors': {}}
    try:
        envelope = fetcher(dict(control, _verify_stop=final))
        sync['connected'] = True
        sync['last_success_at'] = sync['attempted_at']
        sync['errors'] = envelope.get('errors', {})
        for name, data in envelope['files'].items():
            atomic_json(root / 'remote' / name, data)
            sync['files'][name] = {'synced_at': sync['attempted_at'],
                                  'updated_at': data.get('updated_at') if isinstance(data, dict) else None}
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        sync['errors'] = {'communication': str(exc)}
    documents = {name: read_json(root / 'remote' / name) for name in FILES}
    snapshot = build_snapshot(control, documents, sync, previous, final)
    snapshot['local_publication'] = publication_summary(root, control['campaign_id'])
    if final:
        state = envelope.get('container_state') if sync['connected'] else None
        snapshot['gpu_stop'] = {'status': 'stop_unverified', 'container': control.get('container'),
                                'checked_at': utcnow(), 'container_state': state}
        if isinstance(state, dict) and state.get('Running') is False:
            snapshot['gpu_stop']['status'] = 'stopped'
            snapshot['gpu_stop']['source'] = 'docker inspect State.Running=false'
        elif isinstance(state, dict) and state.get('Running') is True:
            snapshot['gpu_stop']['status'] = 'still_running'
        snapshot['gpu_stop']['watchdog_stop'] = read_json(root / 'remote' / 'watchdog-stop.json')
        fresh_stop = envelope.get('files', {}).get('watchdog-stop.json') if sync['connected'] else None
        if state is None and isinstance(fresh_stop, dict) and fresh_stop.get('returncode') == 0:
            snapshot['gpu_stop']['status'] = 'stopped'
            snapshot['gpu_stop']['source'] = 'fresh watchdog-stop.json: docker stop returncode=0'
    atomic_json(root / 'snapshot.json', snapshot)
    return snapshot


def cell(value):
    if value is None or value == '' or value == [] or value == {}:
        return '—'
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value.replace('|', '\\|').replace('\n', '<br>')


def metric_summary(metrics):
    if not isinstance(metrics, dict) or not metrics:
        return '尚无本次实测'
    if metrics.get('valid_for_adoption') is False:
        return '候选验证失败，不可采用；历史配对值不计有效收益。完整证据见同名 JSON 报告。'
    original = metrics.get('original_screen') or {}
    measurement = original.get('measurement') or original
    values = []
    samples = measurement.get('samples') or []
    good = [s['result'] for s in samples if isinstance(s.get('result'), dict) and s['result'].get('correct') is True]
    graph = [s['time_us'] for s in good if isinstance(s.get('time_us'), (float, int))]
    if graph:
        values.append('原始 screen %d/%d 正确；HIP graph %.5f–%.5f us' % (len(good), len(samples), min(graph), max(graph)))
    elif measurement.get('time_us') is not None:
        values.append('原始 screen %s us；正确性 %s' % (measurement['time_us'], measurement.get('correct')))
    op_rows = [r for s in good for r in ((s.get('detail') or {}).get('runner') or {}).get('op_test', {}).get('rows', [])]
    distributions = {(r.get('data_init'), r.get('scale_init')) for r in op_rows}
    op_label = 'op_test（多分布 aggregate screen）' if len(distributions) > 1 else 'op_test'
    op = [r['asm us'] for r in op_rows if isinstance(r.get('asm us'), (float, int))]
    if op:
        values.append('%s %.5f–%.5f us' % (op_label, min(op), max(op)))
    candidates = [row for row in metrics.get('candidate_screens', []) if isinstance(row, dict)
                  and row.get('correct') is True and isinstance(row.get('hip_graph'), dict)
                  and type(row['hip_graph'].get('median_us')) in (int, float)
                  and math.isfinite(row['hip_graph']['median_us']) and row['hip_graph']['median_us'] > 0]
    if candidates:
        best = min(candidates, key=lambda row: row['hip_graph']['median_us'])
        values.append('候选 screening（未独立确认）：HIP graph 中位数最低的正确候选 %s，'
                      'HIP graph %.5f us，%s %s us，有效样本 %s；筛选值不代表已确认收益' % (
                          best.get('candidate_id'), best['hip_graph']['median_us'],
                          op_label, (best.get('op_test') or {}).get('median_us', '未记录'), best.get('valid_samples')))
    for pair in metrics.get('paired_results', []):
        if pair.get('stage') == 'final' and (pair.get('scope') == 'independent_paired' or pair.get('independent') is True):
            values.append('final %s：gain=%s%%，%s 对，%s（reference=%s）' % (
                pair.get('method'), pair.get('gain_pct'), pair.get('pairs'), pair.get('verdict'), pair.get('reference_id')))
    decision = metrics.get('campaign_decision') or (metrics.get('final') or {}).get('status')
    if decision:
        values.append('当前 workload 决定：' + str(decision))
    return '；'.join(values) or '已记录本次证据；完整字段见同名 JSON 报告。'


def outcome_summary(snapshot):
    """Summarize final evidence without deriving gains from screening medians."""
    workload_scope = snapshot.get('row_identity') == 'workload'
    adopted, retained = [], []
    for row in snapshot['kernels']:
        metrics = row.get('metrics') or {}
        if not isinstance(metrics, dict) or row.get('status') not in FINISHED:
            continue
        final = metrics.get('final') or {}
        decision = metrics.get('campaign_decision') or final.get('status')
        if metrics.get('valid_for_adoption') is True and decision in (
                'final_recommended', 'confirmed_gain', 'candidate_adopted', 'candidate_selected', 'adopted', 'winner_confirmed'):
            adopted.append(row)
        elif decision in ('original_retained', 'retained_original') and metrics.get('valid_for_adoption') is not False:
            retained.append(row)
    states = snapshot['counts']['by_status']
    lines = ['## 成果摘要', '',
             '已采用 **%d**；保留原始 **%d**；阻塞 **%d**；覆盖待核实（coverage_pending）**%d**；'
             '待排队（pending）**%d**；调优中 **%d**。' % (
                 len(adopted), len(retained), states.get('blocked', 0), states.get('coverage_pending', 0),
                 states.get('pending', 0), states.get('tuning', 0)), '',
             '下表仅列已通过采用门槛的对象；百分比来自 final 阶段、明确以 original 为参考的独立配对比值统计，'
             '不是两列中位数的直接比值。', '',
             ('| 已确认胜出的 workload / .co | 最终原始基线配对结果 | 已取回的本机产物 |' if workload_scope else
              '| 已采用 .co | 最终原始基线配对结果 | 已取回的本机产物 |'), '|---|---|---|']
    local = snapshot.get('local_exports') or {}
    files = local.get('files', []) if local.get('status') == 'verified' else []
    for row in adopted:
        values = []
        for pair in row['metrics'].get('paired_results', []):
            if pair.get('stage') != 'final' or pair.get('reference_id') != 'original':
                continue
            if pair.get('scope') != 'independent_paired' and pair.get('independent') is not True:
                continue
            gain = pair.get('gain_pct')
            measured = isinstance(gain, (int, float)) and not isinstance(gain, bool) and math.isfinite(gain)
            values.append('%s：%s（%s 对，%s）' % (
                pair.get('method', '未记录方法'), ('%+.5f%%' % gain) if measured else '未记录配对收益',
                pair.get('pairs', '未记录'), pair.get('verdict', '未记录判定')))
        links = []
        for artifact in files:
            if artifact.get('co') != row['co'] or artifact.get('verified') is not True:
                continue
            if row.get('task_id') and artifact.get('task_id') != row['task_id']:
                continue
            relative = Path(artifact.get('path', ''))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            full = Path(snapshot['local_output']) / 'exports' / relative
            if full.is_file() and full.stat().st_size == artifact.get('size_bytes'):
                links.append('[%s](%s)' % (cell(relative.name), quote('exports/' + relative.as_posix())))
        lines.append('| %s | %s | %s |' % (
            cell((str(row.get('task_id') or row.get('workload_id')) + ' / ' if workload_scope else '') + row['co']),
            '<br>'.join(cell(value) for value in values) or '未记录符合条件的 final 原始基线配对摘要',
            ' · '.join(links) or '尚未取回；远端路径见下方明细'))
    if not adopted:
        lines += ['', '当前尚无通过全部采用门槛并正式采用的候选。']
    return lines + ['']


def markdown_report(snapshot, final=False):
    count = snapshot['counts']
    lines = ['# %s · %s' % (snapshot['campaign_id'], '最终报告' if final else '进度报告'), '',
             '- 报告时间：' + snapshot.get('report_written_at', snapshot['generated_at']),
             '- 报告槽时间：' + str(snapshot.get('scheduled_report_at', '即时报告')),
             '- 快照同步开始：' + snapshot['generated_at'],
             '- 停止条件：' + stop_condition_label(snapshot),
             '- 远端状态更新时间：' + str(snapshot['remote_updated_at']),
             '- 最近成功通信：' + str(snapshot['sync']['last_success_at']),
             '- 当前通信：' + ('已连接' if snapshot['sync']['connected'] else '失败；以下为最后同步记录'),
             '- GPU 停止核验：' + str(snapshot.get('gpu_stop', {}).get('status', 'not_checked')),
             '- 阶段 / 状态：%s / %s' % (snapshot['phase'], snapshot['status']),
             '- 当前步骤：' + str(snapshot.get('active_step')),
             '- 当前 .co：' + str(snapshot['current_co']),
             '- 当前 workload/task：' + str(snapshot.get('current_task_id')),
             '- 已知 %d；本次范围 %d；范围外 %d；完成 %d；待完成 %d' % (
                 count['known'], count['target_count'], count['out_of_scope'], count['finished'], count['remaining']),
             '- 远端产物目录：' + snapshot['remote_output'],
             '- 本机目录：' + snapshot['local_output'], '']
    if snapshot.get('completion'):
        lines += ['尝试与关联比较进度：`%s`。已尝试不等于通过完成验收；失败与待适配项仍保留在未完成清单。' %
                  cell(snapshot['completion']), '']
    if snapshot.get('adapter_coverage'):
        coverage = snapshot['adapter_coverage']
        lines += ['适配覆盖原因：来自 `%s` 的 **%d** 个 .co 原始原因，见 '
                  '[adapter-coverage-reasons.csv](adapter-coverage-reasons.csv)。'
                  '这是适配覆盖记录，部分对象另有显式可运行任务；不表示全部未调优，也不与 CSV 覆盖数量合并。' %
                  (cell(coverage['source']), coverage['count']), '']
    if snapshot.get('local_publication'):
        publication = snapshot['local_publication']
        lines += ['本机发布回执（只读主管索引）：状态 `%s`；成功 **%s**；错误 **%s**；最新 commit `%s`。' %
                  (cell(publication.get('status')), cell(publication.get('published')),
                   cell(publication.get('error_count')), cell(publication.get('latest_commit'))), '']
    if snapshot.get('row_identity') == 'workload':
        lines += ['计数单位为独立 workload；同一 .co 的不同尺寸不会合并。', '',
                  'CSV 覆盖：`%s`。全部未调优 workload 与 .co 原因分别保存为 '
                  '[remaining-workloads.csv](remaining-workloads.csv) 和 [co-coverage.csv](co-coverage.csv)。' %
                  cell(snapshot.get('coverage_counts')), '']
    if snapshot.get('winner'):
        winner = snapshot['winner']
        assessed = winner.get('coverage_assessment') or winner.get('assess_summary') or winner.get('assess') or {}
        summary = {k: winner.get(k) for k in ('task_id', 'co', 'scope')}
        if isinstance(assessed, dict):
            assessed_counts = assessed.get('counts') or {}
            summary['coverage'] = {'status': assessed.get('status'),
                'unsupported': assessed_counts.get('unsupported', assessed.get('unsupported')),
                'nonregression_pass': assessed_counts.get('pass', assessed.get('nonregression'))}
        else:
            summary['coverage'] = '详见 JSON 证据'
        lines += ['胜出仅限已验证 workload，不代表同 .co 的其他用途已通过覆盖验证。', '',
                  '胜出与覆盖摘要：`%s`。完整记录和产物路径见同名 JSON 报告。' % cell(summary), '']
    if snapshot['sync']['errors']:
        lines += ['通信 / 文件错误：`%s`' % cell(snapshot['sync']['errors']), '']
    if isinstance(snapshot.get('diagnostic'), dict) and snapshot['diagnostic']:
        lines += ['## 独立诊断', '', '独立诊断不计入候选采用或 .co 完成数。', '',
                  '```json', json.dumps(snapshot['diagnostic'], ensure_ascii=False, indent=2), '```', '']
    if snapshot.get('diagnostic_history'):
        lines += ['### 历史独立诊断', '', '```json',
                  json.dumps(snapshot['diagnostic_history'], ensure_ascii=False, indent=2), '```', '']
    local_diagnostic = snapshot.get('local_diagnostic_sync') or {}
    if local_diagnostic:
        lines += ['本机诊断同步：`%s`；只取显式诊断 JSON 引用，不作为采用证据。' %
                  cell(local_diagnostic.get('status')), '']
        if local_diagnostic.get('status') == 'verified':
            for item in local_diagnostic.get('files', []):
                relative = 'diagnostics/%s/%s' % (snapshot['diagnostic']['id'], item['path'])
                lines.append('- [%s](%s) · SHA256 `%s`' % (
                    cell(item['path']), quote(relative), cell(item['sha256'])))
            lines += ['']
        if local_diagnostic.get('errors'):
            lines += ['诊断同步说明：`%s`' % cell(local_diagnostic['errors']), '']
    if final:
        lines += ['停止核验证据：`%s`' % cell(snapshot.get('gpu_stop')), '',
                  '监控结束不等同 GPU 停止。若远端仍报告 tuning/running，视为截止时可能中断且尚未发布终态；待完成清单保留。', '']
    lines += outcome_summary(snapshot)
    if final:
        groups = progress_breakdown(snapshot)
        lines += ['## 最终工作覆盖分类', '',
                  '以下分类依据现有 run、结果阶段和原因字段，不改远端原始 status；blocked 不等同于未尝试。', '',
                  ('| 分类 | workload 数量 |' if snapshot.get('row_identity') == 'workload' else '| 分类 | .co 数量 |'), '|---|---|']
        lines += ['| %s | %d |' % (STAGE_LABELS[name], len(rows)) for name, rows in groups.items()]
        lines += ['', '全部未完成条目仍在 [remaining.csv](remaining.csv)；分类明细见 '
                  '[remaining-by-stage.csv](remaining-by-stage.csv)。已经调优且保留原始的对象单列于 '
                  '[completed-original-retained.csv](completed-original-retained.csv)。', '']
    lines += ['## 全部运行条目', '',
              '| .co | workload / MNK / CSV来源 | 类别 | 状态 | 原因 | 实测性能（远端原值） | run / 产物 |',
              '|---|---|---|---|---|---|---|']
    for row in snapshot['kernels']:
        metric_text = metric_summary(row.get('metrics'))
        artifacts = '<details><summary>产物路径</summary><pre>%s</pre></details>' % html.escape(
            json.dumps({'run_id': row.get('run_id'), 'artifacts': row.get('artifacts')}, ensure_ascii=False))
        lines.append('| %s |' % ' | '.join(cell(value) for value in (
            row['co'], row.get('workload'), row.get('category'), row.get('status'), row.get('reason'),
            metric_text, artifacts)))
    if not snapshot['kernels']:
        lines += ['', '尚未收到远端 inventory；已知数量为 0，不代表远端没有 .co。']
    lines += ['', '## 待完成运行条目', '', '| .co | workload ID | 类别 | 状态 | 原因 |', '|---|---|---|---|---|']
    for row in snapshot['remaining']:
        lines.append('| %s |' % ' | '.join(cell(value) for value in (
            row['co'], workloads.key(row), row.get('category'), row.get('status'), row.get('reason'))))
    lines += ['', '性能仅展示本次任务发布的实测字段；空白表示尚无实测。筛选与最终确认以记录状态为准。', '']
    return '\n'.join(lines)


def write_report(control, snapshot, final=False):
    root = Path(control['local_output'])
    snapshot['local_exports'] = read_json(root / 'exports-sync.json', {})
    slot_time = snapshot.get('scheduled_report_at', snapshot['generated_at'])
    snapshot['report_written_at'] = utcnow()
    stamp = datetime.fromtimestamp(timestamp(slot_time), timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stem = 'final-report' if final else 'report-' + stamp
    snapshot['latest_report'] = str(root / (stem + '.md'))
    atomic_json(root / (stem + '.json'), snapshot)
    (root / (stem + '.md')).write_text(markdown_report(snapshot, final), encoding='utf-8')
    with (root / 'reports.jsonl').open('a', encoding='utf-8') as output:
        output.write(json.dumps({'time': slot_time, 'snapshot_at': snapshot['generated_at'],
                                 'written_at': snapshot['report_written_at'], 'final': final,
                                 'report': snapshot['latest_report'], 'counts': snapshot['counts'],
                                 'phase': snapshot['phase'], 'status': snapshot['status'],
                                 'sync': snapshot['sync']}, ensure_ascii=False) + '\n')
    adapter_coverage = snapshot.get('adapter_coverage')
    if adapter_coverage:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['co', 'reason', 'source'])
        writer.writeheader()
        for co, reason in sorted(adapter_coverage['reasons'].items()):
            writer.writerow({'co': co, 'reason': reason, 'source': adapter_coverage['source']})
        (root / 'adapter-coverage-reasons.csv').write_text(output.getvalue(), encoding='utf-8')
    workload_fields = ['task_id', 'workload_id', 'm', 'n', 'k', 'csv_file', 'csv_row'] if snapshot.get('row_identity') == 'workload' else []
    for filename, rows, fields in (
            ('remaining-workloads.csv', snapshot.get('remaining_workloads'),
             ['workload_id', 'co', 'category', 'status', 'reason', 'm', 'n', 'k', 'csv_file', 'csv_row']),
            ('co-coverage.csv', snapshot.get('co_coverage'),
             ['co', 'status', 'reason', 'workload_ids', 'remaining_workload_ids'])):
        if rows is not None:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                values = workloads.csv_fields(row)
                writer.writerow({key: json.dumps(values[key], ensure_ascii=False) if isinstance(values.get(key), list)
                                 else values.get(key, '') for key in fields})
            (root / filename).write_text(output.getvalue(), encoding='utf-8')
    if final:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['co', 'category', 'status', 'reason'] + workload_fields)
        writer.writeheader()
        for row in snapshot['remaining']:
            values = workloads.csv_fields(row)
            writer.writerow({key: values.get(key, '') for key in writer.fieldnames})
        (root / 'remaining.csv').write_text(output.getvalue(), encoding='utf-8')
        groups = progress_breakdown(snapshot)
        fields = ['stage', 'co', 'category', 'status', 'run_id', 'reason'] + workload_fields
        for filename, selected_groups in (
                ('remaining-by-stage.csv', [name for name in groups if not name.startswith('completed_')]),
                ('completed-original-retained.csv', ['completed_original_retained'])):
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for name in selected_groups:
                for row in groups[name]:
                    values = workloads.csv_fields(row)
                    writer.writerow(dict({key: values.get(key, '') for key in fields}, stage=name))
            (root / filename).write_text(output.getvalue(), encoding='utf-8')
        atomic_json(root / 'final-status-breakdown.json', {
            'campaign_id': control['campaign_id'], 'generated_at': snapshot['generated_at'],
            'counts': {name: len(rows) for name, rows in groups.items()}, 'labels': STAGE_LABELS,
            'source': 'remote status/run/stage/reason; original status unchanged; unresolved_stage means insufficient evidence'})
    atomic_json(root / 'snapshot.json', snapshot)
    print(json.dumps({'report': snapshot['latest_report'], 'counts': snapshot['counts'],
                      'phase': snapshot['phase'], 'sync_errors': snapshot['sync']['errors']}, ensure_ascii=False), flush=True)


def success_requested(control, snapshot):
    if control.get('stop_condition') == 'all_runnable_workloads_completed':
        completion = snapshot.get('completion') or {}
        planned = set(snapshot.get('planned_task_ids') or [])
        rows = {workloads.key(row): row for row in snapshot.get('kernels', [])}
        sync = snapshot.get('sync') or {}
        # An attempt may finish with a blocked/coverage-pending result. This
        # closes monitoring only after the runner finishes associated workloads;
        # build_snapshot still retains those failures in the unfinished counts.
        return (sync.get('connected') is True and
                not any(name in (sync.get('errors') or {}) for name in ('plan.json', 'progress.json', 'communication')) and
                snapshot.get('status') == 'completed' and bool(planned) and
                completion.get('all_tasks_attempted') is True and
                completion.get('associations_finished') is True and
                completion.get('total_tasks') == len(planned) and
                completion.get('attempted_tasks') == len(planned) and
                all(rows.get(task_id, {}).get('attempt_finished_at') and
                    rows[task_id].get('status') in FINISHED | {'blocked', 'coverage_pending', 'failed', 'error',
                                                             'seed_failed', 'adapter_failed'}
                    for task_id in planned))
    return (control.get('stop_condition') == 'first_confirmed_winner' and
            snapshot.get('status') == 'winner_confirmed' and isinstance(snapshot.get('winner'), dict) and
            bool(snapshot['winner'].get('task_id') or snapshot['winner'].get('workload_id')))


def stop_condition_label(value):
    if value.get('stop_condition') == 'all_runnable_workloads_completed':
        return '全部可调优任务完成，关联尺寸比较结束并确认专用容器停止；失败与待适配项仍列为未完成'
    if value.get('stop_condition') == 'first_confirmed_winner':
        return '首个严格确认胜出，并确认专用容器停止'
    if value.get('deadline'):
        return str(value['deadline'])
    return '未设置截止时间；停止条件：' + str(value.get('stop_condition') or '未声明')


def finalize(control, snapshot):
    root = Path(control['local_output'])
    snapshot['local_diagnostic_sync'] = sync_diagnostic(control, snapshot.get('diagnostic'), force=True)
    write_report(control, snapshot, final=True)
    exports = sync_exports(control)
    snapshot['local_exports'] = exports
    snapshot['report_finalized_at'] = utcnow()
    atomic_json(root / 'snapshot.json', snapshot)
    atomic_json(root / 'final-report.json', snapshot)
    final_text = markdown_report(snapshot, final=True) + (
        '\n## 本机确认产物\n\n仅按远端 export/manifest.json 的固定清单取回并核验 SHA256。\n\n```json\n' +
        json.dumps(exports, ensure_ascii=False, indent=2) + '\n```\n')
    final_temp = root / 'final-report.md.tmp'
    final_temp.write_text(final_text, encoding='utf-8')
    os.replace(str(final_temp), str(root / 'final-report.md'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--poll-seconds', type=float, default=60)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    control = json.loads(args.control.read_text())
    root = Path(control['local_output'])
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'monitor.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('Another monitor holds this campaign lock')
    (root / 'monitor.pid').write_text(str(os.getpid()) + '\n')
    deadline = timestamp(control['deadline']) if control.get('deadline') else float('inf')
    interval = max(1, float(control.get('report_interval_seconds', 600)))
    started = timestamp(control['started_at'])
    next_report = started + (int(max(0, time.time() - started) // interval) + 1) * interval
    first = True
    while True:
        if time.time() >= deadline:
            # Wait a fixed grace period for the external deadline watchdog to
            # publish its stop result, then begin a NEW read after the deadline.
            time.sleep(max(0, deadline + 5 - time.time()))
            control = json.loads(args.control.read_text())
            snapshot = sync_once(control, final=True)
            finalize(control, snapshot)
            break
        snapshot = sync_once(control)
        if success_requested(control, snapshot):
            snapshot = sync_once(control, final=True)
            state = snapshot.get('gpu_stop', {}).get('container_state') or {}
            if success_requested(control, snapshot) and state.get('Running') is False:
                finalize(control, snapshot)
                break
            snapshot['monitor_status'] = 'running'
            snapshot['awaiting_container_stop'] = True
            atomic_json(root / 'snapshot.json', snapshot)
        snapshot['local_diagnostic_sync'] = sync_diagnostic(control, snapshot.get('diagnostic'))
        atomic_json(root / 'snapshot.json', snapshot)
        now = time.time()
        if now >= deadline:
            continue
        if first or now >= next_report or args.once:
            if now >= next_report:
                snapshot['scheduled_report_at'] = datetime.fromtimestamp(next_report, timezone.utc).isoformat()
            write_report(control, snapshot)
            while next_report <= now:
                next_report += interval
        first = False
        if args.once:
            break
        time.sleep(max(0.05, min(max(1, args.poll_seconds), next_report - time.time(), deadline - time.time())))


if __name__ == '__main__':
    main()
