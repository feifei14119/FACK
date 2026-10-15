"""CPU-only whole-kernel verifier and coverage evidence for campaign decisions."""
import collections
import datetime
import hashlib
from pathlib import Path

from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.model import Kind
from reorder.verifier import Verifier

REPO = Path(__file__).resolve().parents[2]


def engine_fingerprints():
    paths = sorted((REPO / 'reorder').rglob('*.py')) + sorted((REPO / 'isa').rglob('*.py'))
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def audit_source(path, expected_sha256):
    path = Path(path).resolve()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError('static audit source digest changed')
    program = parser.parse(path.read_text())
    target = Gfx942Target.from_program(program)
    analysis = regions.analyze(program, target)
    result = Verifier(target, analysis=analysis).verify(program)
    instructions = list(program.instr_lines())
    lds = target.lds_roundtrip_model(instructions)
    required = any(target.is_lds_load(ln.opcode, ln.operands) for ln in instructions)
    unknown = dict(collections.Counter(ln.opcode for ln in instructions
                   if target.classify(ln.opcode, ln.operands) is Kind.UNKNOWN))
    coverage_complete = not unknown and (not required or lds.resolved)
    status = 'coverage_pending' if not coverage_complete else ('passed' if result.ok else 'rejected')
    return {'path': str(path), 'sha256': actual, 'status': status, 'verify_ok': result.ok,
            'violations': result.violations, 'loop_count': len(analysis.loops),
            'coverage': {'lds_roundtrip_required': required, 'lds_model_resolved': lds.resolved,
                         'lds_stride': lds.stride, 'unknown_opcode_counts': unknown,
                         'complete_for_declared_model': coverage_complete},
            'scope': 'whole-kernel first-iteration and steady-state static model; hardware validation remains required'}


def audit_run(status, candidate_ids):
    artifacts = {}
    for cid in dict.fromkeys(candidate_ids):
        source = status['state']['candidates'][cid]['artifact']
        artifacts[cid] = audit_source(Path(status['run_dir']) / source['path'], source['sha256'])
    return {'schema_version': 1, 'reviewed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'engine_sha256': engine_fingerprints(), 'artifacts': artifacts}


def gate_campaign_decision(decision, audit, valid_candidate_ids, original_artifact):
    """Keep terminal status, selection, and the tri-state adoption flag consistent."""
    decision = dict(decision)
    artifacts = audit['artifacts']
    selected_status = artifacts.get(decision.get('selected_id'), {}).get('status')
    baseline_status = artifacts.get('original', {}).get('status')
    incomplete = (baseline_status in (None, 'coverage_pending') or selected_status in (None, 'coverage_pending')
                  or (not valid_candidate_ids and any(a['status'] == 'coverage_pending' for a in artifacts.values())))
    rejected = (baseline_status == 'rejected' or selected_status == 'rejected'
                or (not valid_candidate_ids and any(a['status'] == 'rejected' for a in artifacts.values())))
    if incomplete or rejected or not valid_candidate_ids:
        reason = ('static_model_coverage_pending' if incomplete else
                  'static_verifier_rejected' if rejected else 'no_valid_candidate')
        decision.update(status='original_retained', selected_id='original',
                        selected_artifact=original_artifact, reason=reason)
        return decision, 'coverage_pending' if incomplete else 'blocked', False if rejected and not incomplete else None
    # False denotes established invalidity, not an ordinary no-gain outcome.
    flag = True if decision['status'] == 'final_recommended' else None
    return decision, 'completed', flag


def export_audit_matches(out, row, decision):
    """Require source-, engine-, and digest-bound passing audit before publication."""
    import json
    metrics = row.get('metrics', {})
    if metrics.get('valid_for_adoption') is not True:
        return False
    audit_path = Path(metrics.get('static_audit_path', '')).resolve()
    if out.resolve() not in audit_path.parents:
        return False
    if hashlib.sha256(audit_path.read_bytes()).hexdigest() != metrics.get('static_audit_sha256'):
        return False
    audit = json.loads(audit_path.read_text())
    if audit.get('engine_sha256') != engine_fingerprints():
        return False
    selected = audit.get('artifacts', {}).get(decision.get('selected_id'), {})
    baseline = audit.get('artifacts', {}).get('original', {})
    return (baseline.get('status') == 'passed' and selected.get('status') == 'passed' and selected.get('verify_ok') is True
            and selected.get('coverage', {}).get('complete_for_declared_model') is True
            and selected.get('sha256') == metrics.get('selected_artifact', {}).get('assembly_sha256'))
