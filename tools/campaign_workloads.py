"""Workload identities and CSV coverage for read-only campaign monitoring."""
from collections import Counter


def key(row):
    return str(row.get('task_id') or row.get('workload_id') or
               (row.get('workload') or {}).get('id') or row.get('co'))


def workload(row):
    value = row.get('workload') or {}
    if isinstance(value, dict) and isinstance(value.get('inputs'), dict):
        return dict(value)
    inputs = row.get('inputs') or {k: v for k, v in value.items()
                                  if k not in ('id', 'csv_file', 'csv_row', 'csv', 'selection')}
    refs = value.get('csv') or []
    if value.get('csv_file'):
        refs = [{'path': value['csv_file'], 'line': value.get('csv_row')}]
    return {'id': row.get('workload_id') or row.get('task_id') or value.get('id'),
            'inputs': inputs, 'csv': refs, 'selection': 'dispatch_csv' if refs else 'recorded_inputs'}


def category(family):
    return 'moe' if 'moe' in str(family).lower() else 'mla' if 'mla' in str(family).lower() else 'gemm'


def reference_row(ref):
    inputs = ref.get('inputs') or {k: v for k, v in (ref.get('effective_row') or ref.get('row') or {}).items()
        if k not in ('us', 'us1', 'us2', 'tflops', 'bw', 'kernelName', 'kernelName1', 'kernelName2')}
    return {'workload_id': ref['workload_id'], 'family': ref.get('family'),
            'category': category(ref.get('family')), 'status': ref.get('status'), 'reason': ref.get('reason'),
            'co': [m['co'] for m in ref.get('matches', [])],
            'workload': {'id': ref['workload_id'], 'inputs': inputs,
                'csv': [dict(ref.get('source') or {}, line=ref.get('line'))], 'selection': 'dispatch_csv'}}


def plan_tasks(plan):
    refs = {ref['workload_id']: ref for ref in plan.get('references', [])}
    rows = []
    for task in plan.get('tasks', []):
        ref = refs.get(task['task_id'], {})
        if ref:
            w = reference_row(ref)['workload']
        else:
            w = workload(task)
            w['selection'] = task.get('source_kind') or w.get('selection') or 'recorded_inputs'
        w.update(inputs=task.get('inputs') or w['inputs'], cu_num=plan.get('cu_num'), dispatch_status='not_checked')
        rows.append(dict(task, workload_id=task['task_id'], workload=w,
                         category=task.get('category') or category(ref.get('family') or task.get('inputs', {}).get('family')),
                         status=task.get('status') or 'pending_original_validation',
                         reason=task.get('reason') or 'not_started: awaiting fresh original validation'))
    return rows


def coverage(plan, kernels, remaining):
    current = {key(row): row for row in kernels}
    completed = set(current) - {key(row) for row in remaining}
    references = []
    for ref in plan.get('references', []):
        row = reference_row(ref)
        actual = current.get(row['workload_id'])
        if actual:
            row.update(status=actual.get('status') or 'pending', reason=actual.get('reason'),
                       task_id=actual.get('task_id'), run_id=actual.get('run_id'))
        references.append(row)
    pending = [row for row in references if row['workload_id'] not in completed]
    by_co = plan.get('co_to_workloads', {})
    co_rows = []
    for co, ids in by_co.items():
        left = [value for value in ids if value not in completed]
        co_rows.append({'co': co, 'workload_ids': ids, 'remaining_workload_ids': left,
            'status': 'workloads_remaining' if left else 'completed_for_recorded_workloads',
            'reason': '%d / %d recorded CSV workloads remain' % (len(left), len(ids))})
    for row in plan.get('unreferenced_co', []):
        co_rows.append({'co': row['co'], 'workload_ids': [], 'remaining_workload_ids': [],
                        'status': 'unreferenced', 'reason': row.get('reason')})
    return {'workload_references': references, 'remaining_workloads': pending, 'co_coverage': co_rows,
            'coverage_counts': {'csv_references': len(references), 'remaining_workloads': len(pending),
                'reference_statuses': dict(Counter(row['status'] for row in references)),
                'known_co': len(co_rows), 'unreferenced_co': len(plan.get('unreferenced_co', []))}}


def csv_fields(row):
    w = workload(row)
    p = w.get('inputs') or {}
    return dict(row, task_id=row.get('task_id'), workload_id=row.get('workload_id') or w.get('id'),
                m=p.get('m', p.get('M')), n=p.get('n', p.get('N')), k=p.get('k', p.get('K')),
                csv_file='; '.join(str(r.get('path', '')) for r in w.get('csv', [])),
                csv_row='; '.join(str(r.get('line', '')) for r in w.get('csv', [])))
