"""Synchronize explicit, bounded diagnostic JSON references; never scan workdirs."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024


def relative_json(value, directory):
    if not isinstance(value, str) or not value.startswith(directory + '/'):
        raise ValueError('diagnostic reference outside declared directory')
    relative = value[len(directory) + 1:]
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or path.suffix != '.json':
        raise ValueError('invalid diagnostic JSON reference')
    return relative


def fetch_diagnostic(control, diagnostic):
    script = '''import base64,hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); directory=sys.argv[2]; queue=[sys.argv[3]]; files=[]; seen=set(); errors=[]; total=0
root.resolve().relative_to(pathlib.Path(sys.argv[4]).resolve())
def references(value):
 if isinstance(value,dict):
  for key,item in value.items():
   if key in ('result_path','comparison_path') and isinstance(item,str): yield item
   elif isinstance(item,(dict,list)): yield from references(item)
 elif isinstance(value,list):
  for item in value: yield from references(item)
while queue:
 rel=queue.pop(0)
 if rel in seen: continue
 seen.add(rel)
 if len(seen)>64: raise ValueError('diagnostic exceeds 64 files')
 p=pathlib.PurePosixPath(rel)
 if p.is_absolute() or '..' in p.parts or chr(92) in rel or p.suffix!='.json': raise ValueError('invalid JSON path')
 path=root/rel; path.resolve().relative_to(root.resolve())
 if path.is_symlink() or path.stat().st_size>2097152: raise ValueError('invalid diagnostic file or size')
 payload=path.read_bytes(); total+=len(payload)
 if total>16777216: raise ValueError('diagnostic exceeds 16 MiB')
 data=json.loads(payload)
 files.append(dict(path=rel,sha256=hashlib.sha256(payload).hexdigest(),size_bytes=len(payload),payload=base64.b64encode(payload).decode()))
 for ref in references(data):
  if ref.startswith(directory+'/'): queue.append(ref[len(directory)+1:])
  else: errors.append('excluded reference outside diagnostic: '+ref)
print(json.dumps(dict(files=files,errors=errors)))
'''
    directory = diagnostic['directory'].rstrip('/')
    relative = relative_json(diagnostic['summary_path'], directory)
    root = control['remote_output'] + '/diagnostics/' + diagnostic['id']
    command = 'python3 -c ' + shlex.quote(script) + ' ' + ' '.join(map(shlex.quote, (
        root, directory, relative, control['remote_output'])))
    process = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2', control['remote'], command],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    if process.returncode:
        raise RuntimeError('diagnostic SSH rc=%d: %s' % (process.returncode, process.stderr.decode()[-1500:]))
    return json.loads(process.stdout)


def sync_diagnostic(control, diagnostic, fetcher=fetch_diagnostic, force=False):
    if not isinstance(diagnostic, dict) or not diagnostic.get('summary_path'):
        return None
    result = {'status': 'failed', 'files': [], 'errors': [], 'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        identifier = diagnostic.get('id', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
            raise ValueError('invalid diagnostic ID')
        directory = str(diagnostic.get('directory', '')).rstrip('/')
        if not directory.endswith('/diagnostics/' + identifier):
            raise ValueError('invalid diagnostic directory')
        relative_json(diagnostic['summary_path'], directory)
        root = Path(control['local_output']) / 'diagnostics' / identifier
        root.resolve().relative_to(Path(control['local_output']).resolve())
        state = root / '.local-sync.json'
        fingerprint = hashlib.sha256(json.dumps(diagnostic, sort_keys=True).encode()).hexdigest()
        try:
            previous = json.loads(state.read_text())
        except (OSError, ValueError):
            previous = {}
        if not force and previous.get('fingerprint') == fingerprint and previous.get('status') == 'verified':
            return previous
        envelope = fetcher(control, diagnostic)
        files = envelope.get('files', [])
        if not isinstance(files, list) or not 1 <= len(files) <= 64:
            raise ValueError('invalid diagnostic file count')
        validated, total = [], 0
        for entry in files:
            relative = relative_json(directory + '/' + entry['path'], directory)
            payload = base64.b64decode(entry['payload'], validate=True)
            total += len(payload)
            if len(payload) > MAX_FILE or total > MAX_TOTAL or len(payload) != entry['size_bytes'] or hashlib.sha256(payload).hexdigest() != entry['sha256']:
                raise ValueError('diagnostic size or SHA256 mismatch')
            path = root / relative
            path.resolve().relative_to(root.resolve())
            validated.append((path, payload, entry))
        for path, payload, entry in validated:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.monitor-tmp')
            temporary.write_bytes(payload)
            os.replace(str(temporary), str(path))
            result['files'].append({key: entry[key] for key in ('path', 'size_bytes', 'sha256')})
        result.update(status='verified', fingerprint=fingerprint, errors=envelope.get('errors', []))
        temporary = state.with_name(state.name + '.tmp')
        temporary.write_text(json.dumps(result, indent=2) + '\n')
        os.replace(str(temporary), str(state))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        result['errors'].append(str(exc))
    return result
