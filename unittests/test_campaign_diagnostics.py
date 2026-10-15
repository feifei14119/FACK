import json
import base64
import hashlib

import pytest

from webUI.campaigns import read_campaigns, read_diagnostic
from tools.aiter_campaign_diagnostics import sync_diagnostic


def fixture(tmp_path):
    root = tmp_path / 'client/aiter/tune_out/campaigns/test'
    local = root / 'diagnostics/original-v1'
    (local / 'original-0').mkdir(parents=True)
    remote = '/remote/diagnostics/original-v1'
    diagnostic = {'id': 'original-v1', 'directory': remote,
                  'summary_path': remote + '/original-execution.json'}
    summary = {'records': [{'repeat': 0, 'result_path': remote + '/original-0/result.json',
                            'times_us': {'hip_graph': 243.1}}], 'candidate_gpu_calls': 0}
    (local / 'original-execution.json').write_text(json.dumps(summary))
    (local / 'original-0/result.json').write_text(json.dumps({'result': {
        'compiled': True, 'correct': None, 'detail': {'runner': {'checks': []}}}}))
    return root, diagnostic, local


def test_original_diagnostic_evidence_is_local_and_preserves_unknown_correctness(tmp_path):
    root, diagnostic, _ = fixture(tmp_path)
    evidence = read_diagnostic(root, diagnostic)
    assert evidence['status'] == 'available'
    assert evidence['summary']['candidate_gpu_calls'] == 0
    assert evidence['records'][0]['correct'] is None
    assert evidence['records'][0]['times_us'] == {'hip_graph': 243.1}
    assert len(evidence['records'][0]['sha256']) == 64


def test_diagnostic_paths_cannot_escape_declared_directory(tmp_path):
    root, diagnostic, local = fixture(tmp_path)
    diagnostic['summary_path'] = diagnostic['directory'] + '/../outside.json'
    with pytest.raises(ValueError):
        read_diagnostic(root, diagnostic)
    diagnostic['summary_path'] = diagnostic['directory'] + '/linked.json'
    outside = tmp_path / 'outside.json'
    outside.write_text('{}')
    (local / 'linked.json').symlink_to(outside)
    with pytest.raises(ValueError):
        read_diagnostic(root, diagnostic)


def test_bad_diagnostic_summary_does_not_hide_progress(tmp_path):
    root, diagnostic, local = fixture(tmp_path)
    (local / 'original-execution.json').write_text('{bad')
    (root / 'snapshot.json').write_text(json.dumps({
        'campaign_id': 'test', 'kernels': [], 'counts': {'finished': 17}, 'diagnostic': diagnostic}))
    campaign = read_campaigns(tmp_path)['campaigns'][0]
    assert campaign['counts']['finished'] == 17
    assert campaign['diagnostic']['local_evidence']['status'] == 'failed'


def test_sync_verifies_bytes_and_unchanged_diagnostic_skips_fetch(tmp_path):
    root, diagnostic, local = fixture(tmp_path)
    payload = b'{"records": []}'
    calls = []
    def fetcher(*args):
        calls.append(True)
        return {'files': [{'path': 'original-execution.json', 'size_bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(), 'payload': base64.b64encode(payload).decode()}]}
    control = {'local_output': str(root)}
    first = sync_diagnostic(control, diagnostic, fetcher)
    second = sync_diagnostic(control, diagnostic, fetcher)
    assert first == second and first['status'] == 'verified'
    assert len(calls) == 1
    assert (local / 'original-execution.json').read_bytes() == payload


def test_sync_rejects_corruption_without_overwriting_evidence(tmp_path):
    root, diagnostic, local = fixture(tmp_path)
    old = (local / 'original-execution.json').read_bytes()
    bad = {'files': [{'path': 'original-execution.json', 'size_bytes': 2,
        'sha256': '0' * 64, 'payload': base64.b64encode(b'{}').decode()}]}
    result = sync_diagnostic({'local_output': str(root)}, diagnostic, lambda *_: bad)
    assert result['status'] == 'failed'
    assert (local / 'original-execution.json').read_bytes() == old
