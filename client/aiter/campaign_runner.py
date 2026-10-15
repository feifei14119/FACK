#!/usr/bin/env python3
"""Persistent, deadline-limited serial campaign around the reviewed aiter client.

Plans and all mutable results live in tune_out. Each manifest supplies an actual
operator adapter; unsupported code objects are never treated as evaluated.
"""
import argparse
import collections
import copy
import csv
import statistics
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
sys.path.insert(0, str(REPO))

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)

class Campaign:
    def __init__(self, out, deadline):
        self.out = out.resolve()
        self.data = json.loads((out / 'progress.json').read_text())
        self.current = None
        self.counter = 0
        self.deadline = datetime.datetime.fromisoformat(deadline).timestamp()
        self.task_deadline = self.deadline

    def save(self):
        self.data['updated_at'] = now()
        self.data['current_co'] = self.current
        ks = self.data['kernels']
        counts = dict(collections.Counter(k['status'] for k in ks))
        counts.update(total=len(ks), target=sum(k['category'] != 'other' for k in ks))
        counts.setdefault('completed', 0)
        counts.setdefault('blocked', 0)
        counts.setdefault('tuning', 0)
        self.data['counts'] = counts
        atomic(self.out / 'progress.json', self.data)
        remaining = [k for k in ks if k['status'] != 'completed' and k['category']!='other']
        atomic(self.out / 'remaining.json', dict(self.data, kernels=remaining))
        for name, rows in [('remaining', remaining), ('out_of_scope', [k for k in ks if k['status']=='out_of_scope'])]:
            path = self.out / (name + '.csv.tmp')
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['co','category','status','reason','run_id','result_stage'], extrasaction='ignore')
                writer.writeheader(); writer.writerows(rows)
            path.replace(self.out / (name + '.csv'))

    def command(self, args, directory, label, timeout=1800, required=True):
        timeout = min(timeout, max(1, self.task_deadline - time.time()))
        self.counter += 1
        stem = directory / ('{:03d}-{}'.format(self.counter, label))
        atomic(stem.with_suffix('.command.json'), {'argv': args, 'started_at': now(), 'timeout': timeout})
        with stem.with_suffix('.stderr.log').open('w') as err, stem.with_suffix('.stdout.log').open('w') as stdout:
            process = subprocess.Popen(args, cwd=str(REPO), stdout=stdout, stderr=err)
            start = time.time()
            while process.poll() is None:
                self.data['active_step'] = label
                self.save()
                if time.time() - start > timeout:
                    import psutil
                    descendants = psutil.Process(process.pid).children(recursive=True)
                    for child in reversed(descendants):
                        try: child.kill()
                        except psutil.NoSuchProcess: pass
                    process.kill()
                    process.wait()
                    raise RuntimeError('command timeout: ' + str(stem))
                time.sleep(5)
        text = stem.with_suffix('.stdout.log').read_text()
        try:
            result = json.loads(text)
        except ValueError:
            result = {'stdout': text, 'returncode': process.returncode}
        atomic(stem.with_suffix('.result.json'), result)
        if required and (process.returncode or 'error' in result):
            raise RuntimeError('{}: {}'.format(label, str(result)[:1000]))
        return result

    def tune(self, task):
        row = next(k for k in self.data['kernels'] if k['co'] == task['co'])
        directory = self.out / 'kernels' / task['id']
        directory.mkdir(parents=True, exist_ok=True)
        self.task_deadline = min(self.deadline, datetime.datetime.fromisoformat(task['deadline']).timestamp())
        self.current = task['co']
        self.data.update(status='running', phase=task['category'])
        row.update(status='tuning', reason='preparing and validating seed', run_id=task['id'], result_stage='seed')
        row['artifacts'] = [str(directory.relative_to(REPO))]
        self.save()
        try:
            seed = directory / 'seed.s'
            if not seed.exists():
                self.command([PYTHON, 'client/aiter/prepare.py', 'gfx942', '--manifest', task['manifest'], '--out', str(seed)], directory, 'prepare')
            advisor = 'selfstudy/gfx942/mfma_issue/skills_out/skills/mfma-interleave-gfx942/scripts/gfx942_advisor.py'
            opcodes = sorted(set(re.findall(r'\b(v_mfma_\w+)', seed.read_text())))
            facts = {}
            for opcode in opcodes:
                facts[opcode] = self.command([PYTHON, advisor, '--facts', opcode[2:] if opcode.startswith('v_') else opcode], directory, 'facts-' + opcode, required=False)
            from agent.session import AgentSession
            from reorder.model import Kind
            editor=AgentSession(seed.read_text(),None,region=task.get('region','loop'))._editor()
            chunks=[[]]
            for iid in editor.order:
                if editor.kind_of(iid) in (Kind.BRANCH,Kind.BARRIER): chunks.append([])
                else: chunks[-1].append(iid)
            block=max(chunks,key=lambda ids:sum(editor.kind_of(i)==Kind.MFMA for i in ids))
            straight=directory/'straight-block.s'
            straight.write_text('\n'.join(editor._line_of[i].raw for i in block)+'\n')
            atomic(directory/'straight-block.json',{'instruction_ids':block,'sha256':hashlib.sha256(straight.read_bytes()).hexdigest(),'scope':'one straight segment; no whole-loop timeline claim'})
            self.command([PYTHON, advisor, '--assembly', str(straight)], directory, 'assembly-coverage', required=False)
            policy = directory / 'comparison-policy.json'
            atomic(policy, {'method':'paired_sign_v1', 'confirm_pairs':8, 'final_pairs':8,
                            'min_gain':0.01, 'alpha':0.05, 'max_confirmations':2})
            params = ['--manifest', task['manifest'], '--python', PYTHON, '--seed', str(task.get('seed', 31415)),
                      '--warmup', '20', '--iters', '100', '--samples', '7', '--timeout', '1800',
                      '--output-dir', str(self.out / 'evaluations')]
            for dim, value in task.get('shape', {}).items():
                params.extend(['--' + dim, str(value)])
            run = str(REPO / 'client/aiter/tune_out/runs' / task['id'])
            self.command([PYTHON, 'tools/tune_run.py', 'init', str(seed), '--client', 'aiter/hsa/gfx942',
                          '--run-id', task['id'], '--eval-calls', '96', '--proposal-limit', '24',
                          '--perf-repeats', '3', '--final-reserve', '16', '--wall-seconds', str(max(1, min(2700, self.task_deadline - time.time() - 30))),
                          '--region', task.get('region', 'loop'), '--comparison-policy', str(policy), '--'] + params,
                         directory, 'init')
            row['reason'] = 'validating original with full independent references and op_test when declared'
            original = self.command([PYTHON, 'tools/tune_run.py', 'eval', run, 'original'], directory, 'original')
            atomic(directory / 'original-screen.json', original)
            status = self.command([PYTHON, 'tools/tune_run.py', 'status', run], directory, 'status-original')
            batches = status['state']['batches']
            base = next(b for b in batches.values() if b['candidate_id']=='original')
            if base['status'] != 'measured':
                raise RuntimeError('original validation failed: ' + self.failure_summary(base))
            row.update(reason='seed passed; generating bounded, statically checked candidates', result_stage='screening')
            row['metrics'] = {'original_screen': self.measurement_summary(base.get('measurement') or {}), 'shape': task.get('shape', {}),
                              'scope': 'declared workload only; host loader path is checked, GPU dispatch trace unverified'}
            self.save()
            suggestions = self.command([PYTHON, 'tools/tune_run.py', 'suggest', run, '--n', str(task.get('candidates', 8))], directory, 'suggest')
            obs = suggestions['observation']
            choices, mechanism_report = self.mechanism_choices(seed.read_text(), task.get('region', 'loop'), suggestions, facts, task.get('candidates',8))
            atomic(directory / 'mechanisms.json', mechanism_report)
            measured, attempted, prepared = [], [], []
            for i, suggestion in enumerate(choices):
                spec, hyp = directory / ('spec-{}.json'.format(i)), directory / ('hypothesis-{}.json'.format(i))
                atomic(spec, suggestion['spec'])
                hypothesis = suggestion['hypothesis']
                hypothesis['hypothesis'] += ' Existing gfx942 advisor facts and coverage are archived; local timing estimates do not prove a whole-kernel speedup or dependency safety.'
                atomic(hyp, hypothesis)
                result = self.command([PYTHON, 'tools/tune_run.py', 'prepare', run, '--observation', obs['observation_id'],
                                       '--base-sha256', obs['base_sha256'], '--spec-file', str(spec), '--hypothesis-file', str(hyp)],
                                      directory, 'candidate-{}-prepare'.format(i), required=False)
                cid = result.get('candidate_id')
                if not cid or cid == 'original' or cid in prepared:
                    continue
                mechanism_report.setdefault('materialized',[]).append({'spec':suggestion['spec'],'candidate_id':cid,'candidate_sha256':cid[5:] if cid.startswith('cand_') else None,'base_sha256':obs['base_sha256']})
                atomic(directory/'mechanisms.json',mechanism_report)
                prepared.append(cid)
                outcome = self.command([PYTHON, 'tools/tune_run.py', 'eval', run, cid], directory, 'candidate-{}-screen'.format(i), required=False)
                attempted.append(cid)
                if outcome.get('status') == 'measured': measured.append(cid)
                row['metrics'].update(prepared_candidates=len(prepared), attempted_candidates=len(attempted), valid_measured_candidates=len(measured))
                self.save()
            status = self.command([PYTHON, 'tools/tune_run.py', 'status', run], directory, 'status-screen')
            atomic(directory / 'screen-status.json', status)
            from client.aiter.campaign_audit import audit_run, gate_campaign_decision
            audit = audit_run(status, ['original'] + measured)
            audit = self.with_coverage_obligations(audit, task)
            audit_path = directory / 'static-audit.json'
            atomic(audit_path, audit)
            numerically_valid = list(measured)
            measured = [cid for cid in measured if audit['artifacts'][cid]['status'] == 'passed']
            row['metrics'].update(numerically_valid_candidates=len(numerically_valid),
                                  valid_measured_candidates=len(measured),
                                  static_audit_path=str(audit_path),
                                  static_audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest())
            # Ranking only chooses which fixed candidates receive fresh confirmation;
            # screening values are never included in confirmation/final samples.
            def score(cid):
                bs = [b for b in status['state']['batches'].values() if b['candidate_id']==cid and b['stage']=='screen']
                return (bs[-1].get('measurement') or {}).get('tflops', 0) if bs and bs[-1]['status']=='measured' else 0
            for cid in sorted(set(measured), key=score, reverse=True)[:2]:
                if score(cid) <= score('original') * 1.01:
                    continue
                row.update(reason='fresh interleaved candidate confirmation', result_stage='confirmation')
                self.save()
                self.command([PYTHON, 'tools/tune_run.py', 'confirm', run, cid], directory, 'confirm', required=False)
            row.update(reason='final independent decision; preserve original unless confirmed', result_stage='final')
            final = self.command([PYTHON, 'tools/tune_run.py', 'final', run], directory, 'final')
            status = self.command([PYTHON, 'tools/tune_run.py', 'status', run], directory, 'status-final')
            atomic(directory / 'final-status.json', status)
            row['metrics'].update(final=final, valid_measured_candidates=len(measured))
            method_results = self.comparison_methods(status)
            atomic(directory / 'timing-methods.json', method_results)
            row['metrics']['timing_methods_path'] = str(directory / 'timing-methods.json')
            row['metrics']['paired_results']=self.paired_summary(method_results)
            decision = dict(final)
            final_methods = method_results.get(final.get('comparison_id'), {}).get('methods', {})
            declared_optest=json.loads(Path(task['manifest']).read_text()).get('validation_hook') is True
            final_optests={k:v for k,v in final_methods.items() if k.startswith('op_test:')}
            methods_complete=bool(final_methods) and 'hip_graph' in final_methods and (bool(final_optests) if declared_optest else True)
            if final.get('status') == 'final_recommended' and (not methods_complete or any(v.get('verdict') != 'confirmed_gain' for v in final_optests.values())):
                decision.update(status='original_retained', selected_id='original', selected_artifact=status['state']['candidates']['original']['artifact'], reason='timing_method_disagreement' if methods_complete else 'timing_method_evidence_incomplete')
            decision, terminal_status, adoption_flag = gate_campaign_decision(
                decision, audit, measured, status['state']['candidates']['original']['artifact'])
            atomic(directory / 'decision.json', decision)
            row['metrics']['raw_final_result'] = final
            row['metrics']['final'] = decision
            row['metrics']['campaign_decision'] = decision['status']
            row['metrics']['selected_artifact'] = self.selected_artifact(status, decision)
            row['metrics']['valid_for_adoption'] = adoption_flag
            if terminal_status != 'completed':
                row['metrics']['unadopted_paired_history'] = row['metrics'].pop('paired_results', [])
            row.update(status=terminal_status, reason=decision.get('status', 'original retained') + ': ' + decision.get('reason',''), result_stage='final' if terminal_status == 'completed' else 'static_audit')
            row['artifacts'].append(str((Path(run) / 'state.json').relative_to(REPO)))
        except Exception as exc:
            row.update(status='blocked', reason=str(exc), result_stage=row.get('result_stage', 'seed'))
            atomic(directory / 'failure.json', {'at':now(), 'error':str(exc)})
        self.current = None
        self.save()

    @staticmethod
    def with_coverage_obligations(audit, task, root=REPO):
        """Keep explicit, evidence-bound coverage gaps outside adoption.

        A pending CFG/alias proof is not a diagnosed instruction error. Keep
        the complete raw verifier result alongside the conservative gate.
        Tasks without an explicit obligation retain their existing behavior.
        """
        obligations = task.get('coverage_obligations', [])
        if not obligations:
            return audit
        if not isinstance(obligations, list):
            raise ValueError('coverage_obligations must be a list')
        for obligation in obligations:
            if obligation.get('co') != task['co'] or not obligation.get('reason'):
                raise ValueError('coverage obligation does not bind the selected code object')
            evidence = obligation.get('evidence', [])
            if not evidence:
                raise ValueError('coverage obligation requires retained evidence')
            for item in evidence:
                path = (Path(root) / item['path']).resolve()
                if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError('coverage obligation evidence digest changed')
        result = copy.deepcopy(audit)
        result['coverage_obligations'] = copy.deepcopy(obligations)
        for artifact in result['artifacts'].values():
            artifact['raw_static_status'] = artifact['status']
            artifact['raw_static_coverage'] = copy.deepcopy(artifact['coverage'])
            artifact['coverage'] = copy.deepcopy(artifact['coverage'])
            artifact['status'] = 'coverage_pending'
            artifact['coverage']['complete_for_declared_model'] = False
            artifact['coverage']['unresolved_obligations'] = [o['reason'] for o in obligations]
        return result

    @staticmethod
    def failure_summary(batch):
        measurement=batch.get('measurement') or {}
        for sample in measurement.get('samples', []):
            result=sample.get('result') or {}
            detail=result.get('detail') or {}
            runner=detail.get('runner') or {}
            if runner.get('correct') is False:
                failed=[check for check in runner.get('checks',[]) if check.get('passed') is False]
                return 'full-output numerical failure: ' + json.dumps(failed)[:1200]
            error=runner.get('error') or detail.get('error')
            log=detail.get('runner_log') or detail.get('log_path')
            if not log and detail.get('work_dir'):
                log=str(Path(detail['work_dir'])/'runner.log')
            if error and 'process exited' in str(error) and log and Path(log).is_file():
                faults=[line for line in Path(log).read_text().splitlines() if 'Memory access fault' in line]
                if faults:return faults[-1][-1200:]+'; '+str(error)[-250:]
            if error:
                lines=str(error).strip().splitlines()
                return lines[-1][-1500:]
            if log and Path(log).is_file():
                lines=Path(log).read_text().splitlines()
                faults=[line for line in lines if 'Memory access fault' in line or 'Error:' in line]
                if faults:return faults[-1][-1500:]
        return str(measurement.get('error') or batch.get('status') or 'unknown evaluation failure')[:1500]

    @staticmethod
    def mechanism_choices(source, region, suggestions, facts, limit):
        from agent.session import AgentSession
        from reorder.model import Kind
        session = AgentSession(source, None, region=region, protect_prefetch=True)
        editor = session._editor()
        obs = suggestions['observation']
        anchors = obs['facts']['anchors']
        slots = obs['facts']['slots']
        current = {f['iid']:row['slot'] for row in slots for f in row['fillers']}
        kinds = {f['iid']:f['kind'] for row in slots for f in row['fillers']}
        report = {'mfma_facts':facts, 'accepted':[], 'rejected':[],
                  'limits':['advisor does not establish AccVGPR or arbitrary operand safety',
                            'control-flow and unknown opcodes prevent exact whole-kernel estimates',
                            'engine dependency, wait and prefetch checks plus complete GPU outputs remain mandatory']}
        choices=[]
        occupied_valu = {row['slot']:sum(f['kind']=='valu' for f in row['fillers']) for row in slots}
        free_valu = any(isinstance(v,dict) and v.get('valu_free',1e9)<v.get('interval',0) for v in facts.values())
        for suggestion in suggestions['suggestions']:
            spec=suggestion['spec']
            if spec['kind']!='layout':
                report['rejected'].append({'spec':spec,'reason':'no MFMA gap mechanism established'})
                continue
            target, ids=next(iter(spec['layout'].items())); target=int(target); iid=ids[0]
            kind=kinds.get(iid); instruction=editor._line_of[iid].raw.strip(); reason=None
            if kind in ('vmem_load','ds_read','smem') and suggestion['direction']=='memory_early':
                reason='Advance this operand load within its engine-checked legal window to increase latency overlap before its consumer. Preserve VMEM/LDS ordering, lgkmcnt semantics and prefetch protection; no memory latency is inferred from the MFMA timing table.'
            elif kind=='salu':
                reason='Redistribute independent scalar address/control arithmetic into an MFMA gap; the gfx942 issue rules permit unrelated SALU overlap, unlike ordinary VALU. Engine checks must preserve SCC and address dependencies.'
            elif kind=='valu' and (free_valu or (occupied_valu.get(current.get(iid),0)==1 and occupied_valu.get(target,0)>0)):
                reason=('Test a VALU placement within the exported class release window.' if free_valu else 'The exported MFMA class has no ordinary VALU release slot: cluster this sole VALU into an already occupied gap to reduce the number of separate MFMA gaps exposed to VALU issue contention.')
            if reason is None:
                report['rejected'].append({'spec':spec,'instruction':instruction,'reason':'no useful exported-window or operand-read hypothesis for this move'})
                continue
            value=dict(suggestion)
            value['hypothesis']=dict(suggestion['hypothesis'],hypothesis=instruction+'; '+reason,
                expected_observable='Lower full-kernel event time under fresh independent confirmation; local interval evidence alone is insufficient.')
            choices.append(value); report['accepted'].append({'spec':spec,'instruction':instruction,'kind':kind,'source_gap':current.get(iid),'target_gap':target,'mechanism':reason})
        # Existing suggest enumerates VALU before later scalar chains. Explicitly
        # examine a bounded set of independent SALU operations for empty gaps.
        positions={iid:i for i,iid in enumerate(editor.order)}
        tested=0
        for iid in editor.order:
            if editor.kind_of(iid)!=Kind.SALU or iid in editor._fences or iid not in current: continue
            for target in range(max(0,current[iid]-3),current[iid]):
                if len(choices)>=limit or tested>=48: break
                tested+=1
                if target>=len(anchors)-1: continue
                if sum(f['kind']=='salu' for f in slots[target]['fillers'])>=3: continue
                layout={target:[iid]}; validation=session.propose([layout])[0]
                if not validation.legal or validation.skipped: continue
                spec={'kind':'layout','region':region,'layout':{str(target):[iid]}}
                if any(c['spec']==spec for c in choices): continue
                instruction=editor._line_of[iid].raw.strip()
                reason='Move an independent scalar address/control operation from a crowded tail into an earlier MFMA gap with fewer than three SALU instructions. Preserve engine SCC/register/address constraints; MFMA class issue facts motivate scalar overlap only.'
                hypothesis={'hypothesis':instruction+'; '+reason,'expected_observable':'Lower confirmed event time without any output/loader change','direction':'salu_gap_balance','source':'observation','evidence_refs':[{'kind':'observation','id':obs['observation_id']}]}
                choices.append({'spec':spec,'hypothesis':hypothesis,'direction':'salu_gap_balance'})
                report['accepted'].append({'spec':spec,'instruction':instruction,'kind':'salu','source_gap':current.get(iid),'target_gap':target,'mechanism':reason})
            if len(choices)>=limit or tested>=48: break
        # A one-instruction move in a long unrolled loop can be below the
        # predeclared 1% threshold. Test at most two repeated, independently
        # checked mechanisms across its existing barrier-separated stages.
        grouped=[]
        for kind_set,direction,explanation in [
            ({Kind.VMEM_LOAD,Kind.DS_READ},'repeated_operand_prefetch','Advance legal operand loads by one MFMA gap across the existing unrolled stages to increase overlap with outstanding memory latency; preserve all barrier/wait and address dependencies.'),
            ({Kind.SALU},'repeated_salu_balance','Distribute legal scalar address/control updates across earlier MFMA gaps in repeated unrolled stages; exported MFMA rules motivate independent SALU overlap, with SCC/register ordering checked by the engine.')]:
            layout={};moved=[];trials=0
            for iid in editor.order:
                if editor.kind_of(iid) not in kind_set or iid not in current or iid in editor._fences:continue
                target=current[iid]-1
                if target<0 or target>=len(anchors)-1:continue
                trials+=1
                if trials>64 or len(moved)>=12:break
                trial=dict(layout)
                trial[target]=list(trial.get(target,[]))+[iid]
                validation=session.propose([trial])[0]
                if not validation.legal or validation.skipped:continue
                layout=trial;moved.append(iid)
            if len(moved)<2:continue
            spec={'kind':'layout','region':region,'layout':{str(k):v for k,v in layout.items()}}
            hypothesis={'hypothesis':explanation+' Moved IIDs: '+str(moved),
                        'expected_observable':'An aggregate full-kernel speedup above the fixed gain threshold with complete outputs unchanged',
                        'direction':direction,'source':'observation','evidence_refs':[{'kind':'observation','id':obs['observation_id']}]}
            grouped.append({'spec':spec,'hypothesis':hypothesis,'direction':direction})
            report['accepted'].append({'spec':spec,'instructions':[editor._line_of[i].raw.strip() for i in moved],'placements':[{'iid':i,'source_gap':current[i],'target_gap':current[i]-1} for i in moved],'mechanism':explanation})
        return (grouped+choices)[:limit],report

    @staticmethod
    def measurement_summary(measurement):
        samples = [s['result'] for s in measurement.get('samples',[]) if s.get('result')]
        times = [s['time_us'] for s in samples if s.get('time_us') is not None]
        return {'status':measurement.get('status'), 'correct':measurement.get('correct'), 'tflops':measurement.get('tflops'),
                'time_us':statistics.median(times) if times else None, 'time_range_us':[min(times),max(times)] if times else None,
                'valid_samples':len(times)}

    @staticmethod
    def selected_artifact(status, final):
        selected = final['selected_id']; state=status['state']
        result = {'assembly':str(Path(status['run_dir']) / final['selected_artifact']['path']),
                  'assembly_sha256':final['selected_artifact']['sha256'], 'code_object':None, 'co_sha256':None}
        attempts = [a for a in state['attempts'].values() if a['candidate_id']==selected and a.get('result') and a['result'].get('correct') is True]
        if attempts:
            evidence=attempts[-1]['result']['detail']['build_evidence']
            artifact=evidence.get('artifact_after_build',{})
            result.update(code_object=artifact.get('path'), co_sha256=artifact.get('sha256'))
        return result

    @staticmethod
    def paired_summary(method_results):
        rows=[]
        for comparison_id,comparison in method_results.items():
            for name,result in comparison.get('methods',{}).items():
                ratio=result.get('median_ratio')
                rows.append({'comparison_id':comparison_id,'stage':comparison['stage'],'method':name,
                             'reference_id':comparison.get('reference_id'), 'candidate_id':comparison.get('candidate_id'),
                             'reference_sha256':comparison.get('reference_sha256'), 'candidate_sha256':comparison.get('candidate_sha256'),
                             'reference_median_us':result.get('reference_median_us'),
                             'candidate_median_us':result.get('candidate_median_us'),
                             'gain_pct':(ratio-1)*100 if ratio is not None else None,
                             'ratio_lower_bound':result.get('lower_ratio_bound'),'ratio_upper_bound':result.get('upper_ratio_bound'),
                             'verdict':result.get('verdict'),'pairs':result.get('pairs'),'scope':'independent_paired'})
        return rows

    @staticmethod
    def comparison_methods(status):
        from client.aiter.compare import summarize
        state=status['state']; policy=status['manifest'].get('comparison_policy')
        results={}
        for cid, comparison in state['comparisons'].items():
            identity = {key:comparison.get(key) for key in ('reference_id','candidate_id','reference_sha256','candidate_sha256')}
            records=[]
            for attempt in state['attempts'].values():
                if attempt.get('comparison_id')!=cid or not attempt.get('result'): continue
                r=attempt['result']; runner=r.get('detail',{}).get('runner',{})
                if r.get('correct') is not True: continue
                times={'hip_graph':r['time_us']}
                for row in runner.get('op_test',{}).get('rows',[]):
                    times['op_test:{}/{}'.format(row['data_init'],row['scale_init'])]=row['asm us']
                records.append({'trial':attempt['pair_index'],'side':attempt['role'],'times_us':times})
            local_policy=dict(policy)
            if comparison.get('stage')=='confirm': local_policy['alpha']=policy['alpha']/policy['max_confirmations']
            try: results[cid]=dict(identity,stage=comparison['stage'],methods=summarize(records,local_policy))
            except (ValueError,KeyError,TypeError) as exc: results[cid]=dict(identity,stage=comparison['stage'],status='incomplete',reason=str(exc))
        return results

    def main(self, plan):
        seen = set()
        phases=['gemm','moe','mla']
        phase_index=phases.index(self.data.get('phase','gemm')) if self.data.get('phase') in phases else 3
        while time.time() < self.deadline - 30:
            configuration=json.loads(plan.read_text())
            if phase_index>=len(phases):
                self.data.update(status='finalizing', phase='summary', active_step='awaiting_hard_stop')
                self.save(); time.sleep(30); continue
            phase=phases[phase_index]
            phase_end=datetime.datetime.fromisoformat(configuration['phase_deadlines'][phase]).timestamp()
            if time.time()>=phase_end-120 or phase in configuration.get('phase_complete',[]):
                for row in self.data['kernels']:
                    if row['category']==phase and row['status']=='pending':
                        row.update(status='blocked', reason=configuration.get('adapter_blocked_reasons',{}).get(row['co'], 'phase_time_budget_exhausted' if time.time()>=phase_end-120 else 'adapter_missing_after_supported_tasks'), result_stage='not_started')
                phase_index+=1
                self.save(); continue
            tasks=configuration['tasks']
            todo = [t for t in tasks if t['category']==phase and t['id'] not in seen and
                    time.time()<datetime.datetime.fromisoformat(t['deadline']).timestamp()-120 and
                    next(k for k in self.data['kernels'] if k['co']==t['co'])['status']=='pending']
            if not todo:
                self.data.update(status='waiting_for_supported_tasks', phase=phase, active_step='adapter_review')
                self.save(); time.sleep(30); continue
            task = todo[0]
            seen.add(task['id'])
            self.tune(task)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--deadline', required=True)
    args = ap.parse_args()
    os.chdir(REPO)
    campaign = Campaign(args.output, args.deadline)
    try:
        campaign.main(args.plan)
    finally:
        campaign.data.update(status='stopped', active_step='deadline' if time.time()>=campaign.deadline-30 else 'runner_exit')
        campaign.current=None
        campaign.save()
