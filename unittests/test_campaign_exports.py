import base64
import hashlib
import json

import pytest

from tools.aiter_campaign_exports import sync_exports, validate_entries
from webUI.campaigns import read_export, read_campaigns


def envelope(payload=b'assembly', path='run/selected.s'):
    return {'manifest': {'campaign_id': 'test', 'files': [
        {'path': path, 'sha256': hashlib.sha256(payload).hexdigest(), 'size_bytes': len(payload)}]},
        'files': {path: base64.b64encode(payload).decode('ascii')}}


@pytest.mark.parametrize('path', ['../selected.s', '/tmp/selected.s', 'run/arbitrary.bin', 'run\\selected.s'])
def test_export_paths_are_confined_to_fixed_allowlist(path):
    with pytest.raises(ValueError):
        validate_entries(envelope(path=path)['manifest'], 'test')


def test_export_checks_local_digest_before_writing(tmp_path):
    value = envelope()
    value['files']['run/selected.s'] = base64.b64encode(b'wrong').decode('ascii')
    result = sync_exports({'local_output': str(tmp_path), 'remote_output': '/remote/task',
                           'campaign_id': 'test'}, fetcher=lambda _: value)
    assert result['status'] == 'failed'
    assert not (tmp_path / 'exports/run/selected.s').exists()


def test_verified_export_records_local_and_remote_paths(tmp_path):
    result = sync_exports({'local_output': str(tmp_path), 'remote_output': '/remote/task',
                           'campaign_id': 'test'}, fetcher=lambda _: envelope())
    assert result['status'] == 'verified'
    assert result['files'][0]['verified'] is True
    assert result['files'][0]['remote_path'] == '/remote/task/export/run/selected.s'
    assert (tmp_path / 'exports/run/selected.s').read_bytes() == b'assembly'


def test_download_requires_manifest_membership_and_rechecks_digest(tmp_path):
    output = tmp_path / 'client/aiter/tune_out/campaigns/test'
    sync_exports({'local_output': str(output), 'remote_output': '/remote/task',
                  'campaign_id': 'test'}, fetcher=lambda _: envelope())
    assert read_export(tmp_path, 'test', 'run/selected.s')['payload'] == b'assembly'
    with pytest.raises(ValueError):
        read_export(tmp_path, '../test', 'run/selected.s')
    with pytest.raises(ValueError):
        read_export(tmp_path, 'test', '../selected.s')
    with pytest.raises(ValueError):
        read_export(tmp_path, 'test', 'unlisted/selected.s')
    (output / 'exports/run/selected.s').write_bytes(b'changed')
    with pytest.raises(ValueError, match='SHA256'):
        read_export(tmp_path, 'test', 'run/selected.s')


def test_broken_export_metadata_does_not_hide_campaign_progress(tmp_path):
    output = tmp_path / 'client/aiter/tune_out/campaigns/test'
    output.mkdir(parents=True)
    (output / 'snapshot.json').write_text(json.dumps({'campaign_id':'test','kernels':[]}))
    (output / 'exports-sync.json').write_text('{broken')
    result=read_campaigns(tmp_path)
    assert result['campaigns'][0]['campaign_id']=='test'
    assert result['campaigns'][0]['local_exports']['status']=='failed'
    assert len(result['errors'])==1


def test_changed_export_archives_previous_verified_bytes_by_sha(tmp_path):
    control={'local_output':str(tmp_path),'remote_output':'/remote/task','campaign_id':'test'}
    first=sync_exports(control,fetcher=lambda _:envelope(b'old metadata','run/comparison.json'))
    second=sync_exports(control,fetcher=lambda _:envelope(b'new metadata','run/comparison.json'))
    assert first['status']==second['status']=='verified'
    archived=second['archived'][0]
    assert archived['previously_verified'] is True
    from pathlib import Path
    assert Path(archived['archive_path']).read_bytes()==b'old metadata'
    assert (tmp_path/'exports/run/comparison.json').read_bytes()==b'new metadata'
    third=sync_exports(control,fetcher=lambda _:envelope(b'new metadata','run/comparison.json'))
    assert third['archived']==[]
    assert len((tmp_path/'export-history.jsonl').read_text().splitlines())==1
