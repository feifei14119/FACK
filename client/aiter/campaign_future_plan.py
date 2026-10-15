#!/usr/bin/env python3
"""Append reviewed MoE-stage1 and unique-tuple MLA decode tasks without running them."""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))


def reviewed_mla_manifest(row, manifest_dir):
    """Build only fixed workloads with reviewed native paging/storage bounds.

    This is an input ABI contract, not a candidate ordering certificate. Every
    new environment must still validate its original before tuning.
    """
    from client.aiter.hsa.gfx942.mla_stage1_driver import (
        STAGE1_METADATA, selected_row, split1_output_format,
        native_page_size, native_kv_tail_padding,
    )
    reviewed = {
        'mla_a8w8_qh8_qseqlen1_gqaratio8_v1.co': ('fp8', 8, 32),
        'mla_a8w8_qh16_qseqlen1_gqaratio16.co': ('fp8', 16, 0),
        'mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co': ('bf16', 8, 0),
        'mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co': ('bf16', 16, 0),
        'mla_dec_stage1_bf16_a16w16_subQ128_mqa128.co': ('bf16', 128, 0),
    }
    if row['co_name'] not in reviewed:
        raise ValueError('fixed page1 workload/global-memory bounds are not reviewed; requires an explicit adapter review')
    dtype, heads, padding = reviewed[row['co_name']]
    fields=('qType','kvType','Gqa','ps','qSeqLen','prefill','causal','lse')
    dispatch={key:row[key] for key in fields}
    expected=(dtype,dtype,str(heads),'0','0' if heads==128 else '1','0','1','0')
    if tuple(dispatch[key] for key in fields) != expected:
        raise ValueError('reviewed MLA catalog tuple changed')
    inputs={'m':384,'n':1024,'k':576,'qseq':1,'dispatch':dispatch,
            'page_size':1,'kv_tail_padding_bytes':padding}
    selected_row(inputs,row['knl_name'])
    native_page_size(inputs)
    native_kv_tail_padding(inputs,row)
    base=REPO/'client/aiter/hsa/gfx942'
    logical_bytes=384*1024*576*(1 if dtype=='fp8' else 2)
    manifest = {
        'schema_version':1,'arch':'gfx942','co':'mla/'+row['co_name'],
        'symbol':row['knl_name'],'catalog':'mla/mla_asm.csv','selection':dispatch,
        'driver':os.path.relpath(base/'mla_stage1_driver.py',manifest_dir),
        'inputs':inputs,'atol':0.005,'rtol':0.02,'validation_hook':True,
        'upstream_resources':['aiter/ops/attention.py','aiter/mla.py',
            'csrc/py_itfs_cu/asm_mla.cu','op_tests/test_mla.py','aiter/test_common.py'],
        'resources':{'mla_schema:'+name:os.path.relpath(base/'mla_codegen_metadata'/name,manifest_dir)
                     for name in STAGE1_METADATA},
        'native_output_abi':{'native_split_count':1,'output_dtype':split1_output_format(row),
            'output_pointer':'ptr_R at kernarg 0x00','status':'requires_original_validation_in_current_environment'},
        'native_kv_storage':{'page_size':1,'logical_shape':[384,1024,576],
            'tail_padding_bytes':padding,'storage_offset_bytes':0,
            'padding_initialization':'zero' if padding else None,
            'physical_storage_bytes':logical_bytes+padding},
    }
    scratch_lse_bytes = {
        'mla_a16w16_qh8_qseqlen1_gqaratio8_v3.co': 12288,
        'mla_dec_stage1_bf16_a16w16_subQ16_mqa16.co': 24576,
    }.get(row['co_name'])
    if scratch_lse_bytes is not None:
        manifest['native_scratch_lse']={
            'physical_storage_bytes':scratch_lse_bytes,'returned':False,
            'read_by_bound_kernel_or_driver':False,
            'four_wave_same_address_writes':True,
            'value_equality_proven':False,'race_freedom_proven':False,
            'scope':'fixed pinned kernel/driver and workload; no high-level MLA consumer',
        }
    return manifest

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--moe-deadline',required=True)
    ap.add_argument('--mla-deadline',required=True)
    args=ap.parse_args();os.chdir(REPO)
    out=args.output;configs=out/'manifests';configs.mkdir(exist_ok=True)
    p=out/'plan.json';plan=json.loads(p.read_text());new=[];audit={}
    existing={t['co'] for t in plan['tasks']}
    base=Path('client/aiter/hsa/gfx942');up=Path('client/aiter/upstream');hsa=up/'hsa/gfx942'
    for family,tag in [('fp8','Fp8'),('i8','Int8')]:
        cat='fmoe_2stages/fmoe_stage1_bf16_pertoken{}_g1u1.csv'.format(tag)
        rows=list(csv.DictReader((hsa/cat).open()))
        for i,row in enumerate(rows):
            name='moe-stage1-{}-{:03d}-v1'.format(family,i);manifest=configs/(name+'.json')
            co='fmoe_2stages/'+row['co_name']
            if co in existing:continue
            if not (hsa/co).is_file():continue
            n=int(row['tile_n'])*((1024+int(row['tile_n'])-1)//int(row['tile_n']))
            data={'schema_version':1,'arch':'gfx942','co':co,'symbol':row['knl_name'],'catalog':cat,
                  'selection':{'tile_m':int(row['tile_m']),'tile_n':int(row['tile_n'])},
                  'driver':os.path.relpath(base/'moe_stage1_driver.py',configs),
                  'inputs':{'m':1024,'n':n,'k':1024,'family':family,'block_m':int(row['tile_m'])},
                  'atol':0.05,'rtol':0.02,'validation_hook':True,
                  'upstream_resources':['aiter/fused_moe.py','aiter/fused_moe_bf16_asm.py','aiter/ops/moe_op.py',
                                        'csrc/py_itfs_cu/asm_moe_2stage.cu','op_tests/test_moe_2stage.py','aiter/test_common.py']}
            manifest.write_text(json.dumps(data,indent=2)+'\n')
            new.append({'id':name,'co':co,'category':'moe','manifest':str(manifest),'shape':{'m':1024,'n':n,'k':1024},
                        'seed':51001+i,'candidates':4,'deadline':args.moe_deadline,'priority':(0 if int(row['tile_m']) in (32,64,128) else 1,int(row['tile_n']),i%2,family,i)})
    new.sort(key=lambda t:t['priority'])
    for task in new:task.pop('priority')
    cat='mla/mla_asm.csv';rows=list(csv.DictReader((hsa/cat).open()))
    fields=('qType','kvType','Gqa','ps','qSeqLen','prefill','causal','lse')
    known=set()
    for i,row in enumerate(rows):
        co='mla/'+row['co_name'];known.add(co)
        if co in existing:continue
        if not (hsa/co).is_file():continue
        if row['ps']!='0' or row['prefill']!='0' or row['lse']!='0':
            audit[co]='persistent/prefill/LSE ABI and complete scratch reference not yet adapted';continue
        if row['qType']!=row['kvType'] or row['qType'] not in ('bf16','fp8'):
            audit[co]='mixed/DS32 quantized cache ABI not yet adapted';continue
        matches=[r for r in rows if all(r[k]==row[k] for k in fields)]
        if len(matches)!=1:
            audit[co]='catalog tuple is ambiguous; cannot bind exact target symbol';continue
        try:
            data=reviewed_mla_manifest(row,configs)
        except ValueError as exc:
            audit[co]=str(exc);continue
        heads=int(row['Gqa']);qseq=data['inputs']['qseq']
        name='mla-stage1-{:02d}-page1-v1'.format(i);manifest=configs/(name+'.json')
        manifest.write_text(json.dumps(data,indent=2)+'\n')
        evidence=out/'dispatch-evidence';evidence.mkdir(exist_ok=True)
        (evidence/(name+'.json')).write_text(json.dumps({'catalog_row':row,'actual_qseq':qseq,'heads':heads,'split':1,
            'selection':'unique tuple checked by driver before launch and exact symbol/path required by runner',
            'cpp_sha256':hashlib.sha256((up/'csrc/py_itfs_cu/asm_mla.cu').read_bytes()).hexdigest(),
            'branch_ranges':[[157,211],[705,810],[880,985],[1038,1090]],
            'output_dtype':data['native_output_abi']['output_dtype'],
            'page_size':data['inputs']['page_size'],
            'kv_tail_padding_bytes':data['inputs']['kv_tail_padding_bytes'],
            'physical_kv_storage_bytes':data['native_kv_storage']['physical_storage_bytes'],
            'scope':'useful low-level stage1 output; unused scratch-LSE is not returned; no persistent, prefill, high-level suite'},indent=2))
        new.append({'id':name,'co':co,'category':'mla','manifest':str(manifest),'shape':{'m':384,'n':1024,'k':576},
                    'seed':62001+i,'candidates':4,'deadline':args.mla_deadline})
    for path in hsa.rglob('*.co'):
        co=path.relative_to(hsa).as_posix()
        if co.startswith('mla/') and co not in known:audit[co]='code object is absent from reviewed dispatch catalog'
        if (co.startswith('fmoe') or co.startswith('topk')) and co not in existing and not any(t['co']==co for t in new):
            audit[co]='fused, weighted, blockscale or routing ABI needs its own complete-output adapter; stage1 validation does not cover it'
    plan['tasks'].extend(t for t in new if t['co'] not in existing)
    plan.setdefault('adapter_blocked_reasons',{}).update(audit)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(plan,indent=2)+'\n');tmp.replace(p)
    (out/'adapter-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps({'moe_tasks':sum(t['category']=='moe' for t in new),'mla_tasks':sum(t['category']=='mla' for t in new),'audited_unsupported':len(audit)}))

if __name__=='__main__':main()
