"""Fetch only a campaign's explicit, bounded export manifest and verify SHA256."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
from datetime import datetime, timezone

NAMES = {'selected.co', 'selected.s', 'comparison.json', 'summary.json', 'comparison-summary.json'}
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024


def validate_entries(manifest, campaign_id):
    if not isinstance(manifest, dict) or manifest.get('campaign_id') != campaign_id:
        raise ValueError('export campaign identity mismatch')
    entries = manifest.get('files')
    if not isinstance(entries, list) or len(entries) > 200:
        raise ValueError('invalid export file list')
    total, seen = 0, set()
    for entry in entries:
        path = entry.get('path', '')
        rel = PurePosixPath(path)
        if not path or rel.is_absolute() or '..' in rel.parts or '\\' in path or rel.name not in NAMES:
            raise ValueError('export path is outside the fixed file allowlist: ' + path)
        if path in seen or not re.fullmatch('[0-9a-f]{64}', entry.get('sha256', '')):
            raise ValueError('invalid or duplicate export identity')
        seen.add(path)
        size = entry.get('size_bytes')
        if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_FILE:
            raise ValueError('invalid export size')
        total += size
        if total > MAX_TOTAL:
            raise ValueError('export total exceeds 128 MiB')
    return entries


def read_remote_exports(control):
    # Both sides validate paths. No archive extraction, glob, or arbitrary
    # artifact traversal is used; stdout is captured without logging file data.
    script = '''import base64, hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / "export"
manifest_path = root / "manifest.json"
if root.is_symlink() or manifest_path.is_symlink() or manifest_path.stat().st_size > 1048576:
    raise ValueError("invalid export manifest path or size")
manifest = json.loads(manifest_path.read_text())
if manifest.get("campaign_id") != sys.argv[2]:
    raise ValueError("export campaign identity mismatch")
entries = manifest.get("files")
if not isinstance(entries, list) or len(entries) > 200:
    raise ValueError("invalid export file list")
total, files = 0, {}
for entry in entries:
    name = entry["path"]
    rel = pathlib.PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or chr(92) in name or rel.name not in (
            "selected.co", "selected.s", "comparison.json", "summary.json", "comparison-summary.json"):
        raise ValueError("export path outside fixed allowlist")
    path = root / name
    path.resolve().relative_to(root.resolve())
    if path.is_symlink() or path.stat().st_size > 16777216:
        raise ValueError("invalid export file path or size")
    payload = path.read_bytes()
    total += len(payload)
    if total > 134217728 or len(payload) != entry["size_bytes"]:
        raise ValueError("export byte limit or size mismatch")
    if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError("remote export SHA256 mismatch")
    files[name] = base64.b64encode(payload).decode("ascii")
print(json.dumps({"manifest": manifest, "files": files}))
'''
    remote_cmd = 'python3 -c %s %s %s' % (
        shlex.quote(script), shlex.quote(control['remote_output']), shlex.quote(control['campaign_id']))
    proc = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
                           '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                           control['remote'], remote_cmd], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=60, universal_newlines=True)
    if proc.returncode:
        raise RuntimeError('export SSH rc=%d: %s' % (proc.returncode, proc.stderr[-2000:].strip()))
    return json.loads(proc.stdout)


def sync_exports(control, fetcher=read_remote_exports):
    output = Path(control['local_output'])
    result = {'campaign_id': control['campaign_id'], 'checked_at': datetime.now(timezone.utc).isoformat(),
              'status': 'failed', 'files': [], 'errors': [], 'archived': []}
    try:
        previous = json.loads((output / 'exports-sync.json').read_text())
    except (OSError, ValueError):
        previous = {}
    prior_files = previous.get('files', []) if isinstance(previous, dict) else []
    if not isinstance(prior_files, list):
        prior_files = []
    prior_hashes = {row.get('path'): row.get('sha256') for row in prior_files
                    if isinstance(row, dict) and row.get('verified') is True}
    try:
        envelope = fetcher(control)
        manifest = envelope['manifest']
        entries = validate_entries(manifest, control['campaign_id'])
        destination = output / 'exports'
        destination.resolve().relative_to(output.resolve())
        destination.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            payload = base64.b64decode(envelope['files'][entry['path']], validate=True)
            if len(payload) != entry['size_bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
                raise ValueError('local export SHA256 or size mismatch: ' + entry['path'])
            path = destination / entry['path']
            path.resolve().relative_to(destination.resolve())
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.stat().st_size > MAX_FILE:
                    raise ValueError('existing local export exceeds archive size limit')
                old = path.read_bytes()
                old_hash = hashlib.sha256(old).hexdigest()
                if old_hash != entry['sha256']:
                    history = output / 'export-history' / Path(entry['path']).parent / old_hash / path.name
                    history.resolve().relative_to(output.resolve())
                    history.parent.mkdir(parents=True, exist_ok=True)
                    if not history.exists():
                        temporary_history = history.with_name(history.name + '.tmp')
                        temporary_history.write_bytes(old)
                        os.replace(str(temporary_history), str(history))
                    elif hashlib.sha256(history.read_bytes()).hexdigest() != old_hash:
                        raise ValueError('existing export history digest mismatch')
                    archived = {'path': entry['path'], 'archive_path': str(history), 'sha256': old_hash,
                                'size_bytes': len(old), 'previously_verified': prior_hashes.get(entry['path']) == old_hash,
                                'archived_at': datetime.now(timezone.utc).isoformat(), 'replacement_sha256': entry['sha256']}
                    result['archived'].append(archived)
                    with (output / 'export-history.jsonl').open('a', encoding='utf-8') as index:
                        index.write(json.dumps(archived, ensure_ascii=False) + '\n')
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_bytes(payload)
            os.replace(str(temporary), str(path))
            result['files'].append(dict(entry, local_path=str(path),
                                        remote_path=control['remote_output'] + '/export/' + entry['path'],
                                        verified=True))
        (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        result['status'] = 'verified' if entries else 'no_confirmed_exports'
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        result['errors'].append(str(exc))
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'export-history.jsonl').exists():
        result['history_index'] = str(output / 'export-history.jsonl')
    temp = output / 'exports-sync.json.tmp'
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    os.replace(str(temp), str(output / 'exports-sync.json'))
    return result
