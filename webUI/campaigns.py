"""Read locally synchronized campaign snapshots; never contact remote hosts."""
import json
import hashlib
from pathlib import Path
import re

EXPORT_NAMES = {'selected.co', 'selected.s', 'comparison.json', 'summary.json', 'comparison-summary.json'}


def read_diagnostic(root, diagnostic):
    """Read only an explicit local diagnostic summary and its bounded result list."""
    if not isinstance(diagnostic, dict) or not diagnostic.get('summary_path'):
        return None
    identifier = diagnostic.get('id', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise ValueError('invalid diagnostic ID')
    directory = str(diagnostic.get('directory', '')).rstrip('/')
    if not directory or not directory.endswith('/diagnostics/' + identifier):
        raise ValueError('invalid diagnostic directory')
    local_root = Path(root) / 'diagnostics' / identifier
    local_root.resolve().relative_to(Path(root).resolve())

    def read(remote_path):
        if not isinstance(remote_path, str) or not remote_path.startswith(directory + '/'):
            raise ValueError('diagnostic file is outside its declared directory')
        relative = Path(remote_path[len(directory) + 1:])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.json':
            raise ValueError('invalid diagnostic JSON path')
        path = local_root / relative
        path.resolve().relative_to(local_root.resolve())
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('diagnostic JSON exceeds 2 MiB')
        payload = path.read_bytes()
        return json.loads(payload), {'local_path': str(path), 'sha256': hashlib.sha256(payload).hexdigest(),
                                     'size_bytes': len(payload)}

    try:
        summary, source = read(diagnostic['summary_path'])
    except FileNotFoundError:
        return {'status': 'not_synced', 'records': []}
    if not isinstance(summary, dict):
        raise ValueError('invalid diagnostic summary')
    records = summary.get('records') or summary.get('screening') or []
    if not isinstance(records, list) or len(records) > 64:
        raise ValueError('diagnostic record list exceeds 64 entries')
    evidence = {'status': 'available', 'summary': summary, 'source': source, 'records': [], 'errors': []}
    for row in records:
        if not isinstance(row, dict) or not row.get('result_path'):
            continue
        try:
            data, source = read(row['result_path'])
            result = data.get('result') or {}
            detail = result.get('detail') or {}
            runner = detail.get('runner') or {}
            evidence['records'].append(dict(source, name=data.get('name'), repeat=row.get('repeat'),
                status=row.get('status'), times_us=row.get('times_us'), compiled=result.get('compiled'),
                correct=result.get('correct'), checks=runner.get('checks'),
                loader_scope=runner.get('loader_scope'), error=row.get('error')))
        except (OSError, ValueError, AttributeError) as exc:
            evidence['errors'].append({'path': row['result_path'], 'error': str(exc)})
    return evidence


def read_campaigns(repo):
    repo = Path(repo).resolve()
    campaigns, errors = [], []
    paths = list(repo.glob('client/*/tune_out/campaigns/*/snapshot.json'))
    paths += list(repo.glob('client/aiter/tune_out/dispatch-*/snapshot.json'))
    for path in sorted(paths):
        try:
            path.resolve().relative_to(repo)
            if path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('snapshot exceeds 64 MiB')
            value = json.loads(path.read_text())
            if not isinstance(value, dict) or not isinstance(value.get('kernels'), list):
                raise ValueError('invalid campaign snapshot')
            value['snapshot_path'] = str(path)
            from webUI.workloads import extract_workload
            for row in value['kernels']:
                row['workload'] = extract_workload(row, repo)
            if isinstance(value.get('diagnostic'), dict):
                try:
                    value['diagnostic']['local_evidence'] = read_diagnostic(path.parent, value['diagnostic'])
                except (OSError, ValueError, TypeError) as exc:
                    value['diagnostic']['local_evidence'] = {'status': 'failed', 'errors': [str(exc)]}
            export_state = path.parent / 'exports-sync.json'
            if export_state.exists():
                try:
                    export_state.resolve().relative_to(path.parent.resolve())
                    if export_state.stat().st_size > 1024 * 1024:
                        raise ValueError('export metadata exceeds 1 MiB')
                    value['local_exports'] = json.loads(export_state.read_text())
                except (OSError, ValueError) as exc:
                    errors.append({'path': str(export_state), 'error': str(exc)})
                    value['local_exports'] = {'status': 'failed', 'errors': [str(exc)]}
            campaigns.append(value)
        except (OSError, ValueError) as exc:
            errors.append({'path': str(path), 'error': str(exc)})
    campaigns.sort(key=lambda row: row.get('started_at', ''), reverse=True)
    return {'campaigns': campaigns, 'errors': errors}


def read_export(repo, campaign_id, relative_path):
    """Return a verified, manifest-listed local export; never resolve user paths globally."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', campaign_id or '') or campaign_id in ('.', '..'):
        raise ValueError('invalid campaign ID')
    repo = Path(repo).resolve()
    roots = [repo / 'client/aiter/tune_out/campaigns' / campaign_id]
    if campaign_id.startswith('dispatch-'):
        roots.append(repo / 'client/aiter/tune_out' / campaign_id)
    existing = [root for root in roots if (root / 'exports-sync.json').is_file()]
    if len(existing) != 1:
        raise ValueError('campaign export directory missing or ambiguous')
    root = existing[0]
    root.resolve().relative_to(repo)
    relative = Path(relative_path)
    if relative.is_absolute() or '..' in relative.parts or relative.name not in EXPORT_NAMES or '\\' in relative_path:
        raise ValueError('invalid export path')
    state_path = root / 'exports-sync.json'
    state_path.resolve().relative_to(root.resolve())
    if state_path.stat().st_size > 1024 * 1024:
        raise ValueError('export metadata exceeds 1 MiB')
    state = json.loads(state_path.read_text())
    if state.get('status') != 'verified' or state.get('campaign_id') != campaign_id:
        raise ValueError('campaign has no verified local exports')
    entry = next((row for row in state.get('files', []) if row.get('path') == relative_path and row.get('verified') is True), None)
    if not entry:
        raise ValueError('file is not in the verified export manifest')
    path = root / 'exports' / relative
    path.resolve().relative_to(root.resolve())
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('export exceeds 16 MiB')
    payload = path.read_bytes()
    if len(payload) != entry.get('size_bytes') or hashlib.sha256(payload).hexdigest() != entry.get('sha256'):
        raise ValueError('local export failed SHA256 or size verification')
    return {'name': relative.name, 'payload': payload}
