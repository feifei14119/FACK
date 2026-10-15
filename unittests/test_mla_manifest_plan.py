"""New plans must carry the native MLA storage ABI, including sparse metadata."""
import copy
import csv
import hashlib
import json

import pytest

from client.aiter.campaign_future_plan import REPO, reviewed_mla_manifest
from client.aiter.hsa.gfx942.mla_stage1_driver import STAGE1_METADATA


def catalog_row(name):
    catalog=REPO/'client/aiter/upstream/hsa/gfx942/mla/mla_asm.csv'
    with catalog.open() as stream:
        return next(row for row in csv.DictReader(stream) if row['co_name']==name)


@pytest.mark.parametrize('name,padding,physical,output_dtype,scratch_bytes',[
    ('mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co',32,226492448,'bf16',None),
    ('mla_a8w8_qh16_qseqlen1_gqaratio16.co',0,226492416,'bf16',None),
    ('mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co',0,452984832,'fp32',12288),
    ('mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co',0,452984832,'fp32',24576),
    ('mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co',0,452984832,'bf16',None),
])
def test_reviewed_manifest_carries_native_storage_and_exact_metadata(tmp_path,name,padding,physical,output_dtype,scratch_bytes):
    row=catalog_row(name)
    data=reviewed_mla_manifest(row,tmp_path)
    assert data['inputs']['page_size']==1
    assert data['inputs']['kv_tail_padding_bytes']==padding
    assert data['inputs']['qseq']==1
    assert data['native_kv_storage']['physical_storage_bytes']==physical
    assert data['native_output_abi']['output_dtype']==output_dtype
    if scratch_bytes is not None:
        assert data['native_scratch_lse']['physical_storage_bytes']==scratch_bytes
        assert data['native_scratch_lse']['returned'] is False
        assert data['native_scratch_lse']['read_by_bound_kernel_or_driver'] is False
        assert data['native_scratch_lse']['four_wave_same_address_writes'] is True
        assert data['native_scratch_lse']['value_equality_proven'] is False
        assert data['native_scratch_lse']['race_freedom_proven'] is False
    else:
        assert 'native_scratch_lse' not in data
    assert data['native_output_abi']['status']=='requires_original_validation_in_current_environment'
    assert data['validation_hook'] is True
    assert (data['atol'],data['rtol'])==(.005,.02)
    assert (tmp_path/data['driver']).resolve()==REPO/'client/aiter/hsa/gfx942/mla_stage1_driver.py'
    assert set(data['resources'])=={'mla_schema:'+name for name in STAGE1_METADATA}
    for name,expected in STAGE1_METADATA.items():
        resource=tmp_path/data['resources']['mla_schema:'+name]
        assert hashlib.sha256(resource.read_bytes()).hexdigest()==expected


def test_planner_does_not_guess_zero_padding_for_unreviewed_native_object(tmp_path):
    row=catalog_row('mla_a16w16_qh16_m16x4_n16x1_coex0_mask1.co')
    with pytest.raises(ValueError,match='global-memory bounds are not reviewed'):
        reviewed_mla_manifest(row,tmp_path)


def test_planner_rejects_catalog_drift_and_wrong_symbol(tmp_path):
    row=catalog_row('mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co')
    changed=copy.deepcopy(row)
    changed['qSeqLen']='2'
    with pytest.raises(ValueError,match='catalog tuple changed'):
        reviewed_mla_manifest(changed,tmp_path)
    changed=copy.deepcopy(row)
    changed['knl_name']='wrong_symbol'
    with pytest.raises(ValueError,match='uniquely bind'):
        reviewed_mla_manifest(changed,tmp_path)


def test_append_plan_preserves_existing_mla_tasks_and_manifest_bytes(tmp_path,monkeypatch):
    from client.aiter import campaign_future_plan
    configs=tmp_path/'manifests'
    configs.mkdir()
    tasks=[]
    for index,name in enumerate((
        'mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co',
        'mla_a8w8_qh16_qseqlen1_gqaratio16.co',
        'mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co',
        'mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co',
        'mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co',
    )):
        path=configs/('historical-'+str(index)+'.json')
        path.write_bytes(b'{"historical_contract": true}\n')
        tasks.append({'id':'historical-'+str(index),'category':'mla','co':'mla/'+name,'manifest':str(path)})
    (tmp_path/'plan.json').write_text(json.dumps({'tasks':tasks}))
    monkeypatch.chdir(REPO)
    monkeypatch.setattr('sys.argv',['campaign_future_plan','--output',str(tmp_path),
        '--moe-deadline','2026-10-14T18:52:27+00:00','--mla-deadline','2026-10-14T21:22:27+00:00'])
    campaign_future_plan.main()
    after=json.loads((tmp_path/'plan.json').read_text())
    assert [t for t in after['tasks'] if t['category']=='mla']==tasks
    for task in tasks:
        assert (configs/task['manifest']).read_bytes()==b'{"historical_contract": true}\n'
