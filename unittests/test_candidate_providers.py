"""Architecture candidate discovery and complete-chain CPU regression tests."""
import hashlib
from types import SimpleNamespace

import pytest

from agent.directions import _layout_intents, resolve_providers, suggestions, validate_search_policy
from agent.run import RunController, RunError
from agent.session import AgentSession
from isa.gfx942.candidates import _chains, repeated_salu_chains
from search.driver import build_candidate
from unittests.test_run_directions import BUILD_POLICY
from unittests.test_session import MFMA
from unittests.test_tuning_run import CONTRACT, FakeEvaluator


def kernel(stages=3, register_shift=0, prefix=0, blocked_stage=None):
    lines = ['.amdgcn_target "amdgcn-amd-amdhsa--gfx942"', '.text', 'k:']
    lines += ['  v_mov_b32 v%d, 0' % (120 + i) for i in range(prefix)]
    for stage in range(stages):
        lines.append('  s_barrier')
        for anchor in range(5):
            lines.append('  %s v[36:39], a[0:1], a[2:3], v[36:39]' % MFMA)
            if anchor == 3:
                if stage == blocked_stage:
                    lines += ['  s_mov_b32 s%d, 0' % (42 + register_shift), '  v_mov_b32 v117, 0']
                for mask in range(2):
                    lines += [
                        '  s_add_u32 s%d, %d, s%d' % (50 + register_shift, 128 * (mask + 1), 42 + register_shift),
                        '  s_cmp_lt_u32 s%d, s%d' % (50 + register_shift, 43 + register_shift),
                        '  s_cselect_b32 s%d, s%d, 0' % (54 + mask + register_shift, 54 + mask + register_shift)]
            if anchor == 2:
                lines.append('  buffer_load_dword v100, v101, s[0:3], 0 offen')
    return '\n'.join(lines + ['  s_endpgm', ''])


def pool(source, provider, n=16):
    return suggestions(source, 'loop', BUILD_POLICY, n=n, providers=[provider])


def test_repeated_chain_spread_survives_line_and_register_changes():
    for source in (kernel(), '\n\n// relocated source\n' + kernel(register_shift=7, prefix=40)):
        rows = pool(source, 'gfx942_repeated_salu_chains')
        spread = next(r for r in rows if r['direction'] == 'repeated_salu_spread')
        placements = spread['details']['placements']
        assert len(placements) == 6 and all(len(p['iids']) == 3 for p in placements)
        assert len({p['block'] for p in placements}) == 3
        assert [p['source_slot'] - p['target_slot'] for p in placements] == [2, 1] * 3
        session = AgentSession(source, None, protect_prefetch=False)
        ed = session._editor()
        before = [i for i in ed.order if ed.opcode_of(i).startswith('s_')]
        layout = {int(k): v for k, v in spread['spec']['layout'].items()}
        report = session.propose([layout])[0]
        assert report.legal and not report.skipped
        ed.set_gap_layout(ed.anchors(), layout)
        assert before == [i for i in ed.order if ed.opcode_of(i).startswith('s_')]
        built, ok = build_candidate(source, dict(spread['spec'], **BUILD_POLICY))
        assert ok and hashlib.sha256(built.encode()).hexdigest() == spread['candidate_sha256']


def test_carry_and_compare_consumers_stay_in_their_chains():
    source = kernel(stages=1).replace('  s_endpgm', '  s_add_u32 s4, s54, s4\n  s_addc_u32 s5, 0, s5\n  s_endpgm')
    ed = AgentSession(source, None, protect_prefetch=False)._editor()
    opcodes = [[ed.opcode_of(i) for i in chain] for chain in _chains(ed)]
    assert ['s_add_u32', 's_addc_u32'] in opcodes
    assert opcodes.count(['s_add_u32', 's_cmp_lt_u32', 's_cselect_b32']) == 2


def test_one_blocked_occurrence_rejects_the_complete_repeated_intent():
    source = kernel(blocked_stage=1)
    ed = AgentSession(source, None, protect_prefetch=False)._editor()
    assert list(repeated_salu_chains(ed, ed.anchors(), 'loop'))  # hypotheses exist
    assert pool(source, 'gfx942_repeated_salu_chains') == []  # no partial-stage fallback


def test_repeated_loads_use_fence_local_occurrences():
    rows = pool(kernel(), 'gfx942_repeated_operand_prefetch')
    assert rows
    for row in rows:
        assert len(row['details']['placements']) == 3
        assert len({p['block'] for p in row['details']['placements']}) == 3


def test_repeated_prefetch_moves_m0_and_its_load_together():
    source = kernel().replace('  buffer_load_dword v100, v101, s[0:3], 0 offen',
        '  s_mov_b32 m0, s10\n  buffer_load_dword v100, s[0:3], 0 offen lds')
    row = pool(source, 'gfx942_repeated_operand_prefetch')[0]
    ed = AgentSession(source, None, protect_prefetch=False)._editor()
    ed.set_gap_layout(ed.anchors(), {int(k): v for k, v in row['spec']['layout'].items()})
    for placement in row['details']['placements']:
        leader, load = placement['iids']
        assert placement['request_iids'] == [leader]
        assert ed.order.index(load) == ed.order.index(leader) + 1
    assert ed.is_legal()


def test_nonrepeating_region_does_not_invent_stages_or_chains():
    assert pool(kernel(stages=1), 'gfx942_repeated_salu_chains') == []
    assert pool(kernel(stages=1), 'gfx942_repeated_operand_prefetch') == []
    assert pool(kernel(stages=1), 'gfx942_salu_chains')


def test_generic_sampling_reaches_tail_and_keeps_salu_separate_from_valu():
    source = kernel(stages=1, prefix=40)
    rows = suggestions(source, 'loop', BUILD_POLICY, n=32, providers=['generic'])
    assert any(row['direction'] == 'scalar_early' for row in rows)
    source = source.replace('  s_endpgm', '\n'.join('  s_mov_b32 s%d, 0' % i for i in range(80, 110)) + '\n  s_endpgm')
    ed = AgentSession(source, None, protect_prefetch=False)._editor()
    last = next(i for i in ed.order if ed._line_of[i].operands == ['s109', '0'])
    intents = list(_layout_intents(ed, ed.anchors(), 'loop'))
    assert any(last in ids for r in intents for ids in r['spec']['layout'].values())


@pytest.mark.parametrize('policy', [
    {'candidate_providers': []}, {'candidate_providers': 'generic'},
    {'candidate_providers': ['generic', 'generic']}, {'candidate_providers': [True]},
    {'candidate_attempt_limit': True}, {'candidate_attempt_limit': 0},
    {'candidate_attempt_limit': 513}, {'candidate_attempt_limit': None}])
def test_malformed_provider_policy_is_rejected(policy):
    with pytest.raises(ValueError):
        validate_search_policy(policy)


def test_target_without_hook_uses_generic_and_never_another_target(monkeypatch):
    monkeypatch.setattr('isa.registry.target_for_source', lambda source: SimpleNamespace(name='other'))
    assert resolve_providers('source') == ['generic']
    with pytest.raises(ValueError, match='unavailable'):
        resolve_providers('source', ['gfx942_salu_chains'])


def test_provider_policy_frozen_and_unknown_name_fails_before_run_creation(tmp_path):
    policy = {'candidate_providers': ['gfx942_repeated_salu_chains'], 'candidate_attempt_limit': 24}
    run = RunController.create(tmp_path/'run', kernel(), CONTRACT, search_policy=policy, protect_prefetch=False)
    policy['candidate_providers'].clear()
    assert run.status()['manifest']['search_policy']['candidate_providers'] == ['gfx942_repeated_salu_chains']
    assert all(r['provider'] == 'gfx942_repeated_salu_chains' for r in run.suggest()['suggestions'])
    with pytest.raises(ValueError, match='unavailable'):
        RunController.create(tmp_path/'bad', kernel(), CONTRACT,
                             search_policy={'candidate_providers': ['missing']})
    assert not (tmp_path/'bad').exists()


def test_generated_candidates_keep_provenance_digest_and_are_not_resuggested(tmp_path):
    run = RunController.create(tmp_path/'run', kernel(), CONTRACT, protect_prefetch=False,
        perf_repeats=1, search_policy={'candidate_providers': ['gfx942_repeated_salu_chains']})
    run.evaluate('original', FakeEvaluator())
    generated = run.suggest(n=1)
    choice, obs = generated['suggestions'][0], generated['observation']
    prepared = run.prepare(obs['observation_id'], obs['base_sha256'], choice['spec'], hypothesis=choice['hypothesis'])
    assert prepared['status'] == 'prepared'
    assert prepared['candidate_generation']['provider'] == choice['provider']
    assert run.status()['state']['candidates'][prepared['candidate_id']]['artifact']['sha256'] == choice['candidate_sha256']
    before = run.status()['state']['used']
    assert choice['candidate_sha256'] not in {r['candidate_sha256'] for r in run.suggest()['suggestions']}
    assert run.status()['state']['used'] == before
    with pytest.raises(RunError, match='relabelled'):
        run.prepare(obs['observation_id'], obs['base_sha256'], choice['spec'],
                    hypothesis=dict(choice['hypothesis'], direction='different'))


def test_attempt_limit_bounds_candidate_validation(monkeypatch):
    calls, original = [], AgentSession.propose
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(AgentSession, 'propose', counted)
    suggestions(kernel(), 'loop', BUILD_POLICY, n=32, attempt_limit=3)
    assert len(calls) <= 3


def test_campaign_consumes_shared_suggestions_without_rewriting_groups(tmp_path):
    from client.aiter.campaign_runner import Campaign
    source = kernel()
    run = RunController.create(tmp_path/'run', source, CONTRACT, protect_prefetch=False,
        search_policy={'candidate_providers': ['gfx942_repeated_salu_chains']})
    suggested = run.suggest(n=2)
    choices, report = Campaign.mechanism_choices(source, 'loop', suggested, {}, 2)
    assert choices == suggested['suggestions']
    assert report['accepted'][0]['candidate_sha256'] == choices[0]['candidate_sha256']
    choices[0]['spec']['layout'].clear()
    assert suggested['suggestions'][0]['spec']['layout']
    with pytest.raises(ValueError, match='source/region'):
        Campaign.mechanism_choices(source + '\n', 'loop', suggested, {}, 2)
