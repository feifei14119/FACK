"""CPU evidence + real local Git/bare-remote tests. Never run a model or GPU."""
import copy
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from agent.run import RunController
from client.aiter.agent_profile import result_evidence, validation_contract
from client.aiter.publication import publication_candidate
from harness.evaluator import EvalResult
from harness.evidence import BuildEvidence
from tools.publish_run import publication_plan
from tools.result_publication import git, git_file, index_file, publish, digest
from tools.tune_run_report import snapshot_report
from unittests.test_aiter_agent_profile import valid_report, DRIVERS
from unittests.test_paired_validation import POLICY
from unittests.test_session import _SYNTH
from unittests.test_tuning_run import prepare


PUBLICATION = {'mode': 'git_commit_push', 'output_dir': 'client/aiter/co_out', 'readme': 'README.md'}


@pytest.fixture
def ready(tmp_path):
    workload = {'co': 'gemm/example.co', 'symbol': 'kernel', 'inputs': {'m': 32, 'n': 8192, 'k': 7168}}
    config = dict(workload, arch='gfx942', validation_hook=True)
    validation = validation_contract(config, DRIVERS / 'optest_driver.py')
    contract = {'client': 'aiter/hsa/gfx942', 'params': [], 'agent_profile': {
        'arch': 'gfx942', 'workload': workload, 'validation': validation, 'publication': PUBLICATION}}
    run = RunController.create(tmp_path/'run', _SYNTH, contract, perf_repeats=1,
        eval_call_limit=100, final_eval_reserve=16, comparison_policy=POLICY, protect_prefetch=False)
    class Evaluator:
        def evaluate(self, path, with_counters=False):
            original = Path(path).read_text() == _SYNTH
            co = Path(path).with_suffix('.co')
            co.write_bytes(b'\x7fELF' + (b'original' if original else b'optimized'))
            build = BuildEvidence(path)
            build.after_build(str(co))
            evidence = build.finish()
            report = valid_report()
            report.update(time_us=10 if original else 5, co_sha256=digest(co.read_bytes()))
            for row in report['op_test']['rows']:
                row['asm us'] = 12 if original else 6
            return EvalResult(compiled=True, correct=True, tflops=1000/report['time_us'], time_us=report['time_us'],
                detail={'runner': report, 'build_evidence': evidence, 'validation': result_evidence(config, report, evidence)})
    evaluator = Evaluator()
    run.evaluate('original', evaluator)
    cid = prepare(run)['candidate_id']
    run.evaluate(cid, evaluator)
    run.confirm(cid, evaluator)
    run.finalize(evaluator)
    return run


@pytest.fixture
def repository(tmp_path):
    repo, remote = tmp_path/'repo', tmp_path/'remote.git'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.name', 'Publication Test')
    git(repo, 'config', 'user.email', 'publication@example.invalid')
    (repo/'README.md').write_text('# Project\n\n### 调优结果\n')
    (repo/'.gitignore').write_text('*.co\n!/client/aiter/co_out/**/*.co\n')
    (repo/'unrelated.txt').write_text('original\n')
    git(repo, 'add', 'README.md', '.gitignore', 'unrelated.txt')
    git(repo, 'commit', '-m', 'initial')
    git(repo, 'init', '--bare', str(remote))
    git(repo, 'remote', 'add', 'origin', str(remote))
    git(repo, 'push', '-u', 'origin', 'main')
    return repo, remote


def test_plan_revalidates_final_and_exports_the_measured_binary(ready):
    plan, reason = publication_plan(ready.directory)
    assert reason is None and plan['code_object'] == b'\x7fELFoptimized'
    assert plan['relative_path'] == 'gfx942/gemm/example.co'
    assert plan['duration_seconds'] > 0
    assert set(plan['methods']) == {'hip_graph', 'op_test:constant/constant', 'op_test:uniform/auto'}
    assert digest(plan['assembly']) == plan['source_sha256']


@pytest.mark.parametrize('damage', ['loader', 'source', 'missing_method', 'wrong_method_gain'])
def test_damaged_final_evidence_cannot_publish(ready, damage):
    state = ready.status()['state']
    final = state['comparisons'][state['final_result']['comparison_id']]
    if damage in ('missing_method', 'wrong_method_gain'):
        if damage == 'missing_method': del final['methods']['op_test:uniform/auto']
        else: final['methods']['hip_graph']['median_ratio'] = 999
    else:
        batch = state['batches'][final['pairs'][0]['batches']['candidate']]
        sample = state['attempts'][batch['attempt_ids'][0]]['result']
        if damage == 'loader': sample['detail']['runner']['co_sha256'] = '0'*64
        else: sample['detail']['build_evidence']['source_before']['sha256'] = '0'*64
        batch['measurement']['samples'][0]['result'] = copy.deepcopy(sample)
    (ready.directory/'state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError):
        publication_plan(ready.directory)


def test_missing_or_changed_final_binary_is_not_rebuilt(ready):
    report = snapshot_report(ready.directory)
    final = report['comparisons'][report['final_result']['comparison_id']]
    paths = []
    for pair in final['pairs']:
        batch = report['batches'][pair['batches']['candidate']]
        sample = report['attempts'][batch['attempt_ids'][0]]['result']
        paths.append(Path(sample['detail']['build_evidence']['artifact_after_build']['path']))
    for path in paths:
        path.unlink()
    with pytest.raises(ValueError, match='missing'):
        publication_candidate(report)
    paths[0].write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        publication_candidate(report)


def test_original_retained_never_creates_a_publication(tmp_path):
    contract = {'client': 'aiter/hsa/gfx942', 'agent_profile': {'publication': PUBLICATION}}
    run = RunController.create(tmp_path/'retained', _SYNTH, contract, comparison_policy=POLICY, final_eval_reserve=16)
    assert publication_plan(run.directory) == (None, 'no_final_recommendation')
    run.finalize(None)
    assert publication_plan(run.directory) == (None, 'no_final_recommendation')
    assert not (tmp_path/'client').exists()


def test_publish_commits_pushes_and_preserves_staged_and_unstaged_edits(repository, ready):
    repo, remote = repository
    plan, _ = publication_plan(ready.directory)
    (repo/'unrelated.txt').write_text('user staged\n')
    (repo/'README.md').write_text('# User staged heading\n\n### 调优结果\n')
    git(repo, 'add', 'unrelated.txt', 'README.md')
    (repo/'README.md').write_text('# User unstaged heading\n\n### 调优结果\n')
    result = publish(repo, plan)
    assert result['status'] == 'published' and result['cached'] is False
    assert git(remote, 'rev-parse', 'refs/heads/main').decode().strip() == result['commit']
    assert git_file(repo, 'HEAD', 'README.md').startswith(b'# Project\n')
    assert index_file(repo, 'README.md').startswith(b'# User staged heading\n')
    assert (repo/'README.md').read_text().startswith('# User unstaged heading\n')
    assert index_file(repo, 'unrelated.txt') == b'user staged\n'
    assert git_file(repo, 'HEAD', 'unrelated.txt') == b'original\n'
    assert Path(result['code_object']).read_bytes() == b'\x7fELFoptimized'
    record = json.loads(next((repo/'client/aiter/co_out/records').glob('*.json')).read_text())
    assert record['number'] == 1 and record['workload']['inputs']['m'] == 32
    text = git_file(repo, 'HEAD', 'README.md').decode()
    assert 'hip_graph: +100.00%' in text and '耗时' in text and 'm=' not in text
    assert git(repo, 'check-ignore', '--no-index', 'client/aiter/co_out/gfx942/gemm/example.co', allowed=(0, 1)) == b''
    before = git(repo, 'rev-parse', 'HEAD')
    assert publish(repo, plan)['cached'] is True
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert (repo/'README.md').read_text().count('<!-- fack:result:') == 1


def test_distinct_candidates_keep_original_tree_and_immutable_history(repository, ready):
    repo, _ = repository
    first, _ = publication_plan(ready.directory)
    publish(repo, first)
    second = dict(first, code_object=b'\x7fELFanother', co_sha256=digest(b'\x7fELFanother'))
    second['workload'] = dict(first['workload'], inputs={'m': 64, 'n': 8192, 'k': 7168})
    second['inputs_identity'] = {'inputs': second['workload']['inputs'], 'symbol': 'kernel'}
    second['display_inputs'] = second['workload']['inputs']
    publish(repo, second)
    assert publish(repo, second)['cached'] is True
    root = repo/'client/aiter/co_out'
    assert (root/'gfx942/gemm/example.co').read_bytes() == second['code_object']
    records = sorted((json.loads(p.read_text()) for p in (root/'records').glob('*.json')), key=lambda d: d['number'])
    assert [r['number'] for r in records] == [1, 2]
    assert (repo/records[0]['archive_path']).read_bytes() == first['code_object']
    assert (repo/records[1]['archive_path']).read_bytes() == second['code_object']
    # Retrying the older publication cannot roll back the canonical path.
    assert publish(repo, first)['cached'] is True
    assert (root/'gfx942/gemm/example.co').read_bytes() == second['code_object']


def test_same_machine_code_is_not_a_new_publication(ready):
    report = snapshot_report(ready.directory)
    comparison = report['comparisons'][report['final_result']['comparison_id']]
    for pair in comparison['pairs']:
        batch = report['batches'][pair['batches']['reference']]
        sample = report['attempts'][batch['attempt_ids'][0]]['result']
        detail = sample['detail']
        for key in ('artifact_after_build', 'artifact_after_evaluation'):
            detail['build_evidence'][key]['sha256'] = digest(b'\x7fELFoptimized')
        detail['runner']['co_sha256'] = digest(b'\x7fELFoptimized')
    assert publication_candidate(report) is None


def test_failed_push_keeps_one_commit_and_retry_does_not_duplicate(repository, ready):
    repo, remote = repository
    plan, _ = publication_plan(ready.directory)
    git(repo, 'remote', 'set-url', 'origin', str(repo/'missing-remote'))
    with pytest.raises(RuntimeError, match='push failed'):
        publish(repo, plan)
    committed = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'remote', 'set-url', 'origin', str(remote))
    assert publish(repo, plan)['cached'] is True
    assert git(repo, 'rev-parse', 'HEAD') == committed
    assert (repo/'README.md').read_text().count('<!-- fack:result:') == 1


def test_failed_commit_is_retryable_and_concurrent_retry_is_idempotent(repository, ready):
    repo, _ = repository
    plan, _ = publication_plan(ready.directory)
    before = git(repo, 'rev-parse', 'HEAD')
    hook = repo/'.git/hooks/pre-commit'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o755)
    with pytest.raises(RuntimeError, match='commit failed'):
        publish(repo, plan)
    assert git(repo, 'rev-parse', 'HEAD') == before
    hook.unlink()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: publish(repo, plan), range(2)))
    assert sorted(r['cached'] for r in results) == [False, True]
    assert (repo/'README.md').read_text().count('<!-- fack:result:') == 1


@pytest.mark.parametrize('conflict', ['symlink', 'modified_co'])
def test_output_conflicts_do_not_modify_readme_or_commit(repository, ready, conflict):
    repo, _ = repository
    plan, _ = publication_plan(ready.directory)
    path = repo/'client/aiter/co_out/gfx942/gemm/example.co'
    path.parent.mkdir(parents=True)
    if conflict == 'symlink': path.symlink_to(repo/'unrelated.txt')
    else: path.write_bytes(b'user file')
    before = (repo/'README.md').read_bytes(), git(repo, 'rev-parse', 'HEAD')
    with pytest.raises(ValueError): publish(repo, plan)
    assert ((repo/'README.md').read_bytes(), git(repo, 'rev-parse', 'HEAD')) == before
