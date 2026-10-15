#!/usr/bin/env python3
"""Publish only adopted candidates from completed campaign decisions; no GPU work."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from client.aiter.campaign_audit import export_audit_matches


def atomic(path, value):
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def publish_row(out, export, row, files):
    run_id=row['run_id']
    if Path(run_id).name!=run_id:raise ValueError('invalid run id')
    decision=json.loads((out/'kernels'/run_id/'decision.json').read_text())
    if decision.get('status')!='final_recommended':return
    if not export_audit_matches(out, row, decision):return
    comparison=json.loads((out/'kernels'/run_id/'timing-methods.json').read_text())
    methods=comparison.get(decision.get('comparison_id'),{}).get('methods',{})
    # Campaign adapters all require upstream validation: empty/incomplete
    # secondary timing evidence cannot authorize an export.
    if 'hip_graph' not in methods or not any(k.startswith('op_test:') for k in methods) or any(v.get('verdict')!='confirmed_gain' for v in methods.values()):return
    selected=row['metrics']['selected_artifact']
    destination=export/run_id;destination.mkdir(exist_ok=True)
    for source_path,expected,name,kind in [(selected['assembly'],selected['assembly_sha256'],'selected.s','selected_assembly'),
                                           (selected['code_object'],selected['co_sha256'],'selected.co','selected_co')]:
        source=Path(source_path).resolve()
        if out.resolve() not in source.parents:raise ValueError('selected artifact escapes campaign')
        actual=hashlib.sha256(source.read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('selected artifact digest changed')
        target=destination/name
        if not target.exists():
            temp=target.with_suffix(target.suffix+'.tmp');shutil.copyfile(source,temp);temp.replace(target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('export digest mismatch')
        files.append({'path':str(target.relative_to(export)),'sha256':actual,'size_bytes':target.stat().st_size,'co':row['co'],'kind':kind})
    summary=destination/'comparison.json'
    atomic(summary,{'co':row['co'],'run_id':run_id,'metrics':row['metrics'],
                    'timing_methods':json.loads((out/'kernels'/run_id/'timing-methods.json').read_text())})
    files.append({'path':str(summary.relative_to(export)),'sha256':hashlib.sha256(summary.read_bytes()).hexdigest(),
                  'size_bytes':summary.stat().st_size,'co':row['co'],'kind':'comparison'})


def publish(out):
    export=out/'export';export.mkdir(exist_ok=True)
    progress=json.loads((out/'progress.json').read_text())
    files=[]
    errors=[]
    for row in progress['kernels']:
        if row['status']!='completed' or row.get('metrics',{}).get('campaign_decision')!='final_recommended':continue
        try:
            row_files=[]
            publish_row(out, export, row, row_files)
            files.extend(row_files)
        except Exception as exc:
            errors.append({'co':row['co'],'run_id':row.get('run_id'),'error':str(exc)})
    atomic(export/'manifest.json',{'campaign_id':progress['campaign_id'],'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':files,'errors':errors})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--deadline',required=True)
    args=parser.parse_args()
    deadline=datetime.datetime.fromisoformat(args.deadline).timestamp()
    while True:
        try:
            publish(args.output)
        except Exception as exc:
            atomic(args.output/'exporter-error.json', {'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':str(exc)})
        if time.time()>=deadline:break
        time.sleep(min(30,max(0,deadline-time.time())))
