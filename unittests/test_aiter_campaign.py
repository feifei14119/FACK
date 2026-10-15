"""CPU tests for campaign evidence summaries and bounded upstream test loading."""
from pathlib import Path
import tempfile
from unittest.mock import patch
import pytest
from client.aiter.campaign_runner import Campaign
from client.aiter.hsa.gfx942 import gemm_driver
import hashlib
import json


def test_progress_summary_does_not_embed_evaluator_resources():
    report = Campaign.measurement_summary({'status':'measured','correct':True,'tflops':10,
        'samples':[{'result':{'time_us':5,'detail':{'resources':'private-large-payload'}}},
                   {'result':{'time_us':7,'detail':{'resources':'private-large-payload'}}}]})
    assert report['time_us'] == 6
    assert report['time_range_us'] == [5,7]
    assert report['valid_samples'] == 2
    assert 'resources' not in repr(report)


def test_paired_summary_preserves_candidate_reference_identity():
    comparison={'stage':'confirm','reference_id':'cand_incumbent','candidate_id':'cand_next',
                'reference_sha256':'incumbent-sha','candidate_sha256':'next-sha',
                'methods':{'hip_graph':{'median_ratio':0.999,'reference_median_us':293.3166,'candidate_median_us':293.61}}}
    summary=Campaign.paired_summary({'pair-id':comparison})[0]
    assert summary['reference_id']=='cand_incumbent'
    assert summary['reference_sha256']=='incumbent-sha'
    assert summary['candidate_id']=='cand_next'
    assert summary['reference_median_us']==293.3166
    assert summary['candidate_median_us']==293.61


def test_gemm_wrapper_sha_rejects_modified_upstream():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        path=root/gemm_driver.TESTS['bf16'][0]
        path.parent.mkdir(parents=True)
        path.write_text('raise RuntimeError("must never execute")\n')
        with patch.object(gemm_driver,'UPSTREAM',root), pytest.raises(ValueError,match='changed'):
            gemm_driver.benchmark_definitions('bf16')


def test_gemm_wrapper_compiles_only_named_functions():
    for family, (_,_,wrapper) in gemm_driver.TESTS.items():
        code=gemm_driver.benchmark_definitions(family)
        assert set(code.co_names) <= {'perftest','TEST_NUM_ITERS',wrapper,'run_torch','dtypes','bf16','None'}
        assert 'test_gemm' not in code.co_names


def test_mla_unique_tuple_rejects_wrong_symbol_and_unadapted_persistent_mode():
    from client.aiter.hsa.gfx942.mla_stage1_driver import selected_row
    dispatch={'qType':'bf16','kvType':'bf16','Gqa':'16','ps':'0','qSeqLen':'1','prefill':'0','causal':'1','lse':'0'}
    inputs={'dispatch':dispatch,'qseq':1}
    with pytest.raises(ValueError,match='uniquely'):
        selected_row(inputs,'wrong_symbol')
    row=selected_row(inputs,'_ZN5aiter39mla_dec_stage1_bf16_a16w16_subQ16_mqa16E')
    assert row['co_name']=='mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co'
    inputs={'dispatch':dict(dispatch,ps='1',qSeqLen='4'),'qseq':4}
    with pytest.raises(ValueError,match='nonpersistent'):
        selected_row(inputs,'_ZN5aiter42mla_a16w16_qh16_m16x4_n16x1_coex0_mask1_psE')


@pytest.mark.parametrize('heads,qseq,expected',[
    (128,1,'bf16'),(16,1,'fp32'),(16,4,'bf16'),(16,8,'bf16'),(8,1,'fp32'),
])
def test_mla_bf16_native_split1_output_format(heads,qseq,expected):
    import csv
    from client.aiter.hsa.gfx942.mla_stage1_driver import UPSTREAM, selected_row, split1_output_format
    rows=list(csv.DictReader((UPSTREAM/'hsa/gfx942/mla/mla_asm.csv').open()))
    dispatch={'qType':'bf16','kvType':'bf16','Gqa':str(heads),'ps':'0',
              'qSeqLen':str(0 if heads==128 else qseq),'prefill':'0','causal':'1','lse':'0'}
    match=next(r for r in rows if all(r[k]==v for k,v in dispatch.items()))
    row=selected_row({'dispatch':dispatch,'qseq':qseq},match['knl_name'])
    assert split1_output_format(row)==expected


@pytest.mark.parametrize('heads,qseq',[(32,1),(64,2)])
def test_mla_rejects_native_null_output_pointer_before_launch(heads,qseq):
    import csv
    from client.aiter.hsa.gfx942.mla_stage1_driver import UPSTREAM, selected_row
    rows=list(csv.DictReader((UPSTREAM/'hsa/gfx942/mla/mla_asm.csv').open()))
    dispatch={'qType':'bf16','kvType':'bf16','Gqa':str(heads),'ps':'0',
              'qSeqLen':'0','prefill':'0','causal':'1','lse':'0'}
    match=next(r for r in rows if all(r[k]==v for k,v in dispatch.items()))
    with pytest.raises(ValueError,match='ptr_RP'):
        selected_row({'dispatch':dispatch,'qseq':qseq},match['knl_name'])


def test_export_uses_resolved_campaign_run_symlink_and_survives_one_bad_row(tmp_path):
    from client.aiter.campaign_export import publish
    from client.aiter.campaign_audit import audit_source, engine_fingerprints
    out=tmp_path/'campaign';out.mkdir()
    (out/'runs').mkdir();(tmp_path/'runs').symlink_to(out/'runs',target_is_directory=True)
    kernels=out/'kernels';kernels.mkdir()
    rows=[]
    for run_id in ['broken','adopted']:
        directory=kernels/run_id;directory.mkdir()
        (directory/'decision.json').write_text(json.dumps({'status':'final_recommended','comparison_id':'final','selected_id':'candidate'}))
        (directory/'timing-methods.json').write_text(json.dumps({'final':{'methods':{
            'hip_graph':{'verdict':'confirmed_gain'},'op_test:random':{'verdict':'confirmed_gain'}}}}))
        run=out/'runs'/run_id;run.mkdir()
        assembly=run/'candidate.s';assembly.write_text('.text\nkernel:\n  s_endpgm\n')
        co=out/(run_id+'.co');co.write_bytes(b'code object')
        audit=directory/'static-audit.json'
        audit.write_text(json.dumps({'engine_sha256':engine_fingerprints(),'artifacts':{
            'candidate':audit_source(assembly,hashlib.sha256(assembly.read_bytes()).hexdigest()),
            'original':{'status':'passed'}}}))
        rows.append({'co':run_id+'.co','run_id':run_id,'status':'completed','metrics':{
            'campaign_decision':'final_recommended','valid_for_adoption':True,
            'static_audit_path':str(audit),'static_audit_sha256':hashlib.sha256(audit.read_bytes()).hexdigest(),
            'selected_artifact':{
                'assembly':str(tmp_path/'runs'/run_id/'candidate.s'),
                'assembly_sha256':hashlib.sha256(assembly.read_bytes()).hexdigest(),
                'code_object':str(co),'co_sha256': 'wrong' if run_id=='broken' else hashlib.sha256(co.read_bytes()).hexdigest()}}})
    (out/'progress.json').write_text(json.dumps({'campaign_id':'test','kernels':rows}))
    publish(out)
    manifest=json.loads((out/'export/manifest.json').read_text())
    assert len(manifest['files'])==3
    assert {f['co'] for f in manifest['files']}=={'adopted.co'}
    assert manifest['errors'][0]['run_id']=='broken'
    assert (out/'export/adopted/selected.s').read_text()=='.text\nkernel:\n  s_endpgm\n'


def test_campaign_audit_reports_unresolved_lds_as_coverage_pending(tmp_path):
    from client.aiter.campaign_audit import audit_source
    source=tmp_path/'unresolved.s'
    source.write_text('.text\nkernel:\n  buffer_load_dword v0, s[4:7], 0 offen lds\n  s_waitcnt vmcnt(0)\n  s_barrier\n  ds_read_b32 v10, v20\n  s_waitcnt lgkmcnt(0)\n  s_endpgm\n')
    audit=audit_source(source,hashlib.sha256(source.read_bytes()).hexdigest())
    assert audit['status']=='coverage_pending'
    assert audit['coverage']['lds_roundtrip_required'] is True
    assert audit['coverage']['lds_model_resolved'] is False


@pytest.mark.parametrize('baseline,selected,decision_status,expected_status,expected_flag',[
    ('passed','passed','original_retained','completed',None),
    ('passed','passed','final_recommended','completed',True),
    ('coverage_pending','passed','final_recommended','coverage_pending',None),
    ('passed','rejected','final_recommended','blocked',False),
    ('rejected','passed','final_recommended','blocked',False),
])
def test_static_gate_keeps_normal_retained_complete_and_coverage_unadopted(baseline,selected,decision_status,expected_status,expected_flag):
    from client.aiter.campaign_audit import gate_campaign_decision
    selected_id='original' if decision_status=='original_retained' else 'candidate'
    audit={'artifacts':{'original':{'status':baseline},'candidate':{'status':selected}}}
    decision,status,flag=gate_campaign_decision({'status':decision_status,'selected_id':selected_id},audit,['candidate'],{'path':'original.s'})
    assert (status,flag)==(expected_status,expected_flag)
    if expected_status!='completed':
        assert decision['status']=='original_retained' and decision['selected_id']=='original'
    if decision_status=='original_retained':
        assert status=='completed' and flag is not False


@pytest.mark.parametrize('failure',['invalidated','engine_changed','wrong_source','tampered_audit'])
def test_export_audit_rejects_unbound_or_invalidated_evidence(tmp_path,failure):
    from client.aiter.campaign_audit import audit_source, engine_fingerprints, export_audit_matches
    source=tmp_path/'candidate.s';source.write_text('.text\nkernel:\n  s_endpgm\n')
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    evidence={'engine_sha256':engine_fingerprints(),'artifacts':{'candidate':audit_source(source,sha)}}
    path=tmp_path/'audit.json';path.write_text(json.dumps(evidence))
    metrics={'valid_for_adoption':True,'static_audit_path':str(path),'static_audit_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'selected_artifact':{'assembly_sha256':sha}}
    if failure=='invalidated':metrics['valid_for_adoption']=False
    elif failure=='wrong_source':metrics['selected_artifact']['assembly_sha256']='different source'
    elif failure=='engine_changed':
        evidence['engine_sha256']['reorder/waitcnt.py']='old engine';path.write_text(json.dumps(evidence));metrics['static_audit_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    else:path.write_text(path.read_text()+' ')
    assert export_audit_matches(tmp_path,{'metrics':metrics},{'selected_id':'candidate'}) is False


def test_failure_summary_extracts_real_runner_error_after_large_build_evidence():
    batch={'measurement':{'error':'generic missing score','samples':[{'result':{'detail':{
        'build_evidence':{'large':'x'*5000},'runner':{'error':'Traceback...\nRuntimeError: missing CK registry kernel\n'}}}}]}}
    assert Campaign.failure_summary(batch)=='RuntimeError: missing CK registry kernel'


def test_failure_summary_preserves_numerical_failure_before_optest():
    batch={'measurement':{'error':'generic','samples':[{'result':{'detail':{
        'runner':{'correct':False,'checks':[{'case':'seed+0','passed':False,'max_abs_error':[5.09375]}]}}}}]}}
    summary=Campaign.failure_summary(batch)
    assert 'numerical failure' in summary and '5.09375' in summary and 'seed+0' in summary


@pytest.mark.parametrize('category',['gemm','moe','unknown_future_family'])
def test_coverage_obligations_do_not_infer_a_block_from_task_category(category):
    audit={'artifacts':{'original':{'status':'passed'}}}
    assert Campaign.with_coverage_obligations(audit,{'co':'kernel.co','category':category}) is audit


@pytest.mark.parametrize('raw_status',['passed','rejected'])
def test_evidenced_coverage_gap_preserves_raw_report_and_prevents_adoption(tmp_path,raw_status):
    from client.aiter.campaign_audit import gate_campaign_decision
    evidence=tmp_path/'proof.json';evidence.write_text('{"alias_order":"unproved"}')
    task={'co':'kernel.co','coverage_obligations':[{'co':'kernel.co','reason':'LDS alias/order proof pending',
        'evidence':[{'path':'proof.json','sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()}]}]}
    artifact={'status':raw_status,'verify_ok':raw_status=='passed','violations':['raw report retained'],
              'coverage':{'complete_for_declared_model':True,'lds_model_resolved':True}}
    audit={'artifacts':{'original':dict(artifact),'candidate':dict(artifact)}}
    guarded=Campaign.with_coverage_obligations(audit,task,root=tmp_path)
    assert audit['artifacts']['original']['status']==raw_status
    for value in guarded['artifacts'].values():
        assert value['status']=='coverage_pending' and value['raw_static_status']==raw_status
        assert value['violations']==['raw report retained']
        assert value['verify_ok']==artifact['verify_ok']
        assert value['raw_static_coverage']['complete_for_declared_model'] is True
        assert value['coverage']['complete_for_declared_model'] is False
    eligible=[cid for cid,value in guarded['artifacts'].items() if cid!='original' and value['status']=='passed']
    decision,status,flag=gate_campaign_decision({'status':'final_recommended','selected_id':'candidate'},guarded,eligible,{'path':'original.s'})
    assert not eligible and status=='coverage_pending' and flag is None
    assert decision['status']=='original_retained' and decision['selected_id']=='original'


def test_coverage_obligation_rejects_changed_evidence(tmp_path):
    (tmp_path/'proof.json').write_text('changed proof')
    task={'co':'kernel.co','coverage_obligations':[{'co':'kernel.co','reason':'unproved',
        'evidence':[{'path':'proof.json','sha256':'old digest'}]}]}
    with pytest.raises(ValueError,match='digest changed'):
        Campaign.with_coverage_obligations({'artifacts':{}},task,root=tmp_path)


def test_coverage_obligation_cannot_silently_bind_another_kernel():
    task={'co':'kernel.co','coverage_obligations':[{'co':'other.co','reason':'unproved','evidence':[]}]}
    with pytest.raises(ValueError,match='selected code object'):
        Campaign.with_coverage_obligations({'artifacts':{}},task)
