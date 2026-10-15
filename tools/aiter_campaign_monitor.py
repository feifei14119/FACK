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
else:
    from aiter_campaign_exports import sync_exports
    from aiter_campaign_diagnostics import sync_diagnostic

FILES = ('inventory.json', 'progress.json', 'remaining.json')
OPTIONAL_FILES = ('watchdog.json', 'watchdog-stop.json')
FINISHED = {'completed', 'done', 'optimized', 'confirmed_gain',
            'final_recommended', 'original_retained', 'retained_original'}
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
        for name in ('kernels', 'code_objects', 'objects', 'items', 'remaining'):
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
    unfinished = {row['co'] for row in snapshot['remaining']}
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
        if row['co'] not in unfinished:
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
        elif status in ('blocked', 'failed', 'error', 'seed_failed', 'adapter_failed') and (
                stage in ('seed', 'prepare', 'adapter', 'environment', 'initializing') or
                any(marker in reason for marker in ('prepare:', 'original validation failed', 'seed validation failed',
                                                    'adapter failed', 'missing adapter', 'unsupported adapter',
                                                    'manifest not found', 'environment setup failed'))):
            group = 'seed_or_adapter_failed'
        elif row.get('run_id') or metrics or stage in ('candidate', 'screening', 'confirm', 'final'):
            group = 'candidate_or_retest_incomplete'
        elif not row.get('run_id') and status in ('pending', 'queued', 'discovered', ''):
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
for name in ("inventory.json", "progress.json", "remaining.json", "watchdog.json", "watchdog-stop.json"):
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
    remote_cmd = 'python3 -c %s %s %s' % (shlex.quote(script),
                                        shlex.quote(control['remote_output']), shlex.quote(container))
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
    merged = {}
    for name in ('inventory.json', 'remaining.json', 'progress.json'):
        for row in entries(documents.get(name)):
            co = row['co']
            # Remaining lists often contain only identity and reason; do not
            # discard actual measurements already published in progress.
            merged.setdefault(co, {'co': co, 'status': 'pending'}).update(row)
    kernels = sorted(merged.values(), key=lambda row: (str(row.get('category', '')), row['co']))
    targets = [row for row in kernels if in_scope(row)]
    remaining = [row for row in targets if row.get('status') not in FINISHED or not row.get('metrics')
                 or (isinstance(row.get('metrics'), dict) and row['metrics'].get('valid_for_adoption') is False)]
    counts = {}
    for row in kernels:
        state = str(row.get('status', 'pending'))
        counts[state] = counts.get(state, 0) + 1
    return {
        'schema_version': 1, 'campaign_id': control['campaign_id'],
        'started_at': control['started_at'], 'deadline': control['deadline'],
        'phase_deadlines': control.get('phase_deadlines', {}),
        'generated_at': sync['attempted_at'], 'remote_updated_at': progress.get('updated_at'),
        'remote': control['remote'], 'remote_output': control['remote_output'],
        'remote_workspace': control.get('remote_workspace'),
        'container_workspace': '/workspace/FACK',
        'local_output': control['local_output'], 'sync': sync,
        'monitor_status': 'finished' if final else 'running',
        'status': progress.get('status', 'awaiting_remote_state'),
        'phase': progress.get('phase'), 'current_co': progress.get('current_co'),
        'active_step': progress.get('active_step'),
        'diagnostic': progress.get('diagnostic'),
        'diagnostic_history': progress.get('diagnostic_history', []),
        'category_counts': progress.get('category_counts', {}),
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


def outcome_summary(snapshot):
    """Summarize final evidence without deriving gains from screening medians."""
    adopted, retained = [], []
    for row in snapshot['kernels']:
        metrics = row.get('metrics') or {}
        if not isinstance(metrics, dict) or row.get('status') not in FINISHED:
            continue
        final = metrics.get('final') or {}
        decision = metrics.get('campaign_decision') or final.get('status')
        if metrics.get('valid_for_adoption') is True and decision in (
                'final_recommended', 'confirmed_gain', 'candidate_adopted', 'candidate_selected', 'adopted'):
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
             '| 已采用 .co | 最终原始基线配对结果 | 已取回的本机产物 |', '|---|---|---|']
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
            relative = Path(artifact.get('path', ''))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            full = Path(snapshot['local_output']) / 'exports' / relative
            if full.is_file() and full.stat().st_size == artifact.get('size_bytes'):
                links.append('[%s](%s)' % (cell(relative.name), quote('exports/' + relative.as_posix())))
        lines.append('| %s | %s | %s |' % (
            cell(row['co']), '<br>'.join(cell(value) for value in values) or '未记录符合条件的 final 原始基线配对摘要',
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
             '- 截止时间：' + snapshot['deadline'],
             '- 远端状态更新时间：' + str(snapshot['remote_updated_at']),
             '- 最近成功通信：' + str(snapshot['sync']['last_success_at']),
             '- 当前通信：' + ('已连接' if snapshot['sync']['connected'] else '失败；以下为最后同步记录'),
             '- GPU 停止核验：' + str(snapshot.get('gpu_stop', {}).get('status', 'not_checked')),
             '- 阶段 / 状态：%s / %s' % (snapshot['phase'], snapshot['status']),
             '- 当前步骤：' + str(snapshot.get('active_step')),
             '- 当前 .co：' + str(snapshot['current_co']),
             '- 已知 %d；本次范围 %d；范围外 %d；完成 %d；待完成 %d' % (
                 count['known'], count['target_count'], count['out_of_scope'], count['finished'], count['remaining']),
             '- 远端产物目录：' + snapshot['remote_output'],
             '- 本机目录：' + snapshot['local_output'], '']
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
                  '| 分类 | .co 数量 |', '|---|---|']
        lines += ['| %s | %d |' % (STAGE_LABELS[name], len(rows)) for name, rows in groups.items()]
        lines += ['', '全部未完成条目仍在 [remaining.csv](remaining.csv)；分类明细见 '
                  '[remaining-by-stage.csv](remaining-by-stage.csv)。已经调优且保留原始的对象单列于 '
                  '[completed-original-retained.csv](completed-original-retained.csv)。', '']
    lines += ['## 全部已知 .co', '',
              '| .co | 类别 | 状态 | 原因 | 实测性能（远端原值） | run / 产物 |',
              '|---|---|---|---|---|---|']
    for row in snapshot['kernels']:
        metrics = row.get('metrics')
        metric_text = metrics
        if isinstance(metrics, dict) and metrics.get('valid_for_adoption') is False:
            metric_text = '**候选验证失败，不可采用；历史配对值不计有效收益。** ' + json.dumps(metrics, ensure_ascii=False, sort_keys=True)
        lines.append('| %s |' % ' | '.join(cell(value) for value in (
            row['co'], row.get('category'), row.get('status'), row.get('reason'),
            metric_text, {'run_id': row.get('run_id'), 'artifacts': row.get('artifacts')})))
    if not snapshot['kernels']:
        lines += ['', '尚未收到远端 inventory；已知数量为 0，不代表远端没有 .co。']
    lines += ['', '## 待完成 .co', '', '| .co | 类别 | 状态 | 原因 |', '|---|---|---|---|']
    for row in snapshot['remaining']:
        lines.append('| %s |' % ' | '.join(cell(row.get(key)) for key in ('co', 'category', 'status', 'reason')))
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
    if final:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['co', 'category', 'status', 'reason'])
        writer.writeheader()
        for row in snapshot['remaining']:
            writer.writerow({key: row.get(key, '') for key in writer.fieldnames})
        (root / 'remaining.csv').write_text(output.getvalue(), encoding='utf-8')
        groups = progress_breakdown(snapshot)
        fields = ['stage', 'co', 'category', 'status', 'run_id', 'reason']
        for filename, selected_groups in (
                ('remaining-by-stage.csv', [name for name in groups if not name.startswith('completed_')]),
                ('completed-original-retained.csv', ['completed_original_retained'])):
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for name in selected_groups:
                for row in groups[name]:
                    writer.writerow(dict({key: row.get(key, '') for key in fields}, stage=name))
            (root / filename).write_text(output.getvalue(), encoding='utf-8')
        atomic_json(root / 'final-status-breakdown.json', {
            'campaign_id': control['campaign_id'], 'generated_at': snapshot['generated_at'],
            'counts': {name: len(rows) for name, rows in groups.items()}, 'labels': STAGE_LABELS,
            'source': 'remote status/run/stage/reason; original status unchanged; unresolved_stage means insufficient evidence'})
    atomic_json(root / 'snapshot.json', snapshot)
    print(json.dumps({'report': snapshot['latest_report'], 'counts': snapshot['counts'],
                      'phase': snapshot['phase'], 'sync_errors': snapshot['sync']['errors']}, ensure_ascii=False), flush=True)


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
    deadline = timestamp(control['deadline'])
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
            break
        snapshot = sync_once(control)
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
