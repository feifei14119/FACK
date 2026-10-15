#!/usr/bin/env python3
"""Append reviewed GEMM catalog tasks to a campaign plan; no kernel execution."""
import argparse
import csv
import json
import os
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--deadline',required=True)
    args=ap.parse_args()
    os.chdir(REPO)
    out=args.output
    configs=out/'manifests';configs.mkdir(parents=True,exist_ok=True)
    plan_path=out/'plan.json'
    plan=json.loads(plan_path.read_text())
    tasks=[]
    base=Path('client/aiter/hsa/gfx942')
    for family,catalog in [('bf16','bf16gemm/bf16gemm_fp32bf16.csv'),('i8','i8gemm/i8gemm_bf16_perTokenI8.csv')]:
        for index,row in enumerate(csv.DictReader(open('client/aiter/upstream/hsa/gfx942/'+catalog))):
            name='gemm-{}-{:02d}-v1'.format(family,index)
            manifest=configs/(name+'.json')
            co=catalog.rsplit('/',1)[0]+'/'+row['co_name']
            selection={'bPreshuffle':int(row['bPreshuffle'])} if family=='bf16' else {'bpreshuffle':1}
            data={'schema_version':1,'arch':'gfx942','co':co,'symbol':row['knl_name'],'catalog':catalog,
                  'selection':selection,'driver':os.path.relpath(base/'gemm_driver.py',configs),
                  'inputs':{'m':256,'n':256,'k':1024,'family':family,'bpreshuffle':bool(int(row.get('bPreshuffle',row.get('bpreshuffle'))))},
                  'atol':0.05,'rtol':0.02,'validation_hook':True,
                  'upstream_resources':['aiter/ops/gemm_op_a16w16.py' if family=='bf16' else 'aiter/ops/gemm_op_a8w8.py',
                                        'csrc/py_itfs_cu/asm_gemm_a16w16.cu' if family=='bf16' else 'csrc/py_itfs_cu/asm_gemm_a8w8.cu',
                                        'op_tests/test_gemm_a16w16.py' if family=='bf16' else 'op_tests/test_gemm_a8w8.py',
                                        'aiter/test_common.py']}
            manifest.write_text(json.dumps(data,indent=2)+'\n')
            tasks.append({'id':name,'co':co,'category':'gemm','manifest':str(manifest),'shape':{'m':256,'n':256,'k':1024},
                          'seed':42001+index,'candidates':6,'deadline':args.deadline})
    # Each new family gets early representatives before the remaining variants.
    tasks.sort(key=lambda t:(int(t['id'].split('-')[2])>1,t['id']))
    existing={t['co'] for t in plan['tasks']}
    plan['tasks'].extend(t for t in tasks if t['co'] not in existing)
    temp=plan_path.with_suffix('.tmp');temp.write_text(json.dumps(plan,indent=2)+'\n');temp.replace(plan_path)
    print(json.dumps({'added':len([t for t in tasks if t['co'] not in existing]),'total_tasks':len(plan['tasks'])}))

if __name__=='__main__': main()
