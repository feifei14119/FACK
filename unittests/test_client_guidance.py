"""Client/architecture routing is read-only and does not assume an aiter workload."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import client
from client import guidance
from unittests.test_tuning_run import cli


@pytest.fixture
def routed(tmp_path, monkeypatch):
    def skill(name, content):
        path = tmp_path / 'knowledge/skills' / name / 'SKILL.md'
        path.parent.mkdir(parents=True)
        path.write_text(content)
        return path.relative_to(tmp_path).as_posix()
    own = skill('custom', 'Use project benchmark; no CSV or op_test.\n')
    old = skill('arch-old', 'old architecture instructions\n')
    future = skill('arch-future', 'future architecture instructions\n')
    registry = tmp_path / 'knowledge/architectures.json'
    registry.write_text(json.dumps({'gfx942': [old], 'gfx1100': [future]}))
    monkeypatch.setattr(guidance, 'REPO', tmp_path)
    monkeypatch.setattr(guidance, 'ARCHITECTURES', registry)
    declaration = {'skills': [own]}
    module = SimpleNamespace(make_evaluator=lambda ctx: pytest.fail('must not initialize GPU'),
                             agent_profile=lambda ctx: copy.deepcopy(declaration))
    cl = client.Client('custom/task', 'custom', 'task', str(tmp_path), str(tmp_path), module)
    return cl, declaration, tmp_path


def test_client_and_arch_skills_are_composed_without_cross_arch_fallback(routed):
    cl, _, _ = routed
    profile = cl.agent_profile(arch='gfx1100', params=['anything=3'])
    assert [s['role'] for s in profile['skills']] == ['client', 'architecture']
    assert 'future architecture' in profile['skills'][1]['content']
    assert 'old architecture' not in json.dumps(profile)
    assert profile['validation'] is None
    unknown = cl.agent_profile(arch='gfx9999')
    assert unknown['architecture_skill_status'] == 'unavailable'
    assert len(unknown['skills']) == 1


def test_missing_skills_and_arch_mismatch_fail_without_running_tools(routed):
    cl, declaration, root = routed
    declaration['arch'] = 'gfx942'
    with pytest.raises(ValueError, match='disagree'):
        cl.agent_profile(arch='gfx1100')
    (root / declaration['skills'][0]).unlink()
    with pytest.raises(ValueError, match='dependency missing'):
        cl.agent_profile(arch='gfx942')


def test_client_cannot_escape_repository_and_snapshot_preserves_content(routed):
    cl, declaration, root = routed
    item = cl.agent_profile()['skills'][0]
    assert item['sha256'] == hashlib.sha256((root / item['path']).read_bytes()).hexdigest()
    declaration['skills'] = ['../elsewhere/SKILL.md']
    with pytest.raises(ValueError, match='repository-relative'):
        cl.agent_profile()


def test_no_target_is_not_silently_gfx942(routed):
    cl, _, _ = routed
    del cl.module.agent_profile
    profile = cl.agent_profile()
    assert profile['arch'] is None and profile['skills'] == []
    assert profile['client_profile_status'] == 'legacy_score_only'


def test_cli_freezes_guidance_and_skill_drift_blocks_next_evaluation(cli, routed):
    invoke, seed, fake_client, fake, _ = cli
    cl, declaration, root = routed
    fake_client.agent_profile = cl.agent_profile
    initialized = invoke('init', str(seed), '--client', fake_client.spec)
    frozen = initialized['manifest']['evaluation_contract']['agent_profile']
    path = root / declaration['skills'][0]
    path.write_text('Changed instructions\n')
    failure = invoke('eval', initialized['run_dir'], 'original', expected=2)
    assert failure['error']['code'] == 'contract_mismatch'
    assert frozen['skills'][0]['content'] != path.read_text()
    assert not fake.calls


@pytest.mark.parametrize('field,value', [('skills', [42]), ('instructions', 'text'),
                                        ('arch', []), ('requires_workload', 'false'), ('workload', [])])
def test_malformed_declarations_are_rejected(routed, field, value):
    cl, declaration, _ = routed
    declaration[field] = value
    with pytest.raises(ValueError):
        cl.agent_profile()


def test_validation_requirement_drift_blocks_evaluation(cli, routed):
    from unittests.test_client_validation import VALIDATION
    invoke, seed, fake_client, fake, _ = cli
    cl, declaration, _ = routed
    declaration['validation'] = copy.deepcopy(VALIDATION)
    fake_client.agent_profile = cl.agent_profile
    initialized = invoke('init', str(seed), '--client', fake_client.spec)
    declaration['validation']['required_checks'].append('another_check')
    failure = invoke('eval', initialized['run_dir'], 'original', expected=2)
    assert failure['error']['code'] == 'contract_mismatch'
    assert not fake.calls
