const test = require('node:test');
const assert = require('node:assert/strict');
const view = require('./campaign_view.js');

test('screening values and completed counts do not invent a paired gain', () => {
  const html = view.metrics({original_screen: {status:'measured',correct:true,time_us:8,tflops:16.5,valid_samples:3},
    prepared_candidates:5,attempted_candidates:4,valid_measured_candidates:3,
    final:{status:'original_retained',reason:'no_confirmed_candidate'}});
  assert.match(html, /screening/);
  assert.match(html, /8 µs · 16.5 TFLOPS/);
  assert.match(html, /准备 5 \/ 尝试 4 \/ 有效实测 3/);
  assert.match(html, /保留原始/);
  assert.match(html, /尚无独立配对统计/);
  assert.doesNotMatch(html, /0%/);
  assert.match(html, /<details>/);
});

test('paired display uses recorded gain and requires explicit independent evidence', () => {
  let html = view.metrics({paired_results:[{method:'screen',reference_median_us:10,candidate_median_us:8,gain_pct:99}]});
  assert.doesNotMatch(html, /独立配对 · screen/);
  html = view.metrics({paired_results:[{scope:'independent_paired',method:'HIP graph',reference_median_us:10,candidate_median_us:8,gain_pct:17}]});
  assert.match(html, /参考 10 µs \/ 候选 8 µs/);
  assert.match(html, /配对收益 17%/);
  assert.doesNotMatch(html, /25%/);
});

test('chosen assembly and code object include remote host mapping and SHA', () => {
  const text = view.artifacts({artifacts:['client/task/state.json'],metrics:{selected_artifact:{
    assembly:'/workspace/FACK/client/task/selected.s',assembly_sha256:'aaa',
    code_object:'/workspace/FACK/client/task/selected.co',co_sha256:'bbb'}}},
    {remote_workspace:'/data/task/workspace'});
  assert.match(text, /远端宿主路径：\/data\/task\/workspace\/client\/task\/selected.co/);
  assert.match(text, /SHA256：bbb/);
  assert.match(text, /SHA256：aaa/);
});

test('recorded text is escaped in summary and full details', () => {
  const html=view.metrics({campaign_decision:'<img src=x onerror=alert(1)>',final:{reason:'<script>'}});
  assert.doesNotMatch(html, /<img|<script>/);
  assert.match(html, /&lt;img/);
});

test('failed posthoc audit withholds historical paired gains from the summary', () => {
  const html=view.metrics({valid_for_adoption:false,campaign_decision:'confirmed_gain',
    posthoc_static_audit:{reason:'four missing waits'},paired_results:[{scope:'independent_paired',
    method:'hip_graph',gain_pct:4,reference_median_us:100,candidate_median_us:96}]});
  const summary=html.split('<details>')[0];
  assert.match(summary,/候选验证失败，不可采用/);
  assert.doesNotMatch(summary,/配对收益|采用候选|独立配对 ·/);
  assert.match(html, /gain_pct/);
  assert.match(html, /four missing waits/);
});

test('null adoption flag permits a normal retained-original result', () => {
  const html=view.metrics({valid_for_adoption:null,final:{status:'original_retained'}});
  assert.match(html,/最终：保留原始/);
  assert.doesNotMatch(html,/候选验证失败/);
});

test('only explicit original reference is called original and final is prioritized', () => {
  const html=view.metrics({paired_results:[
    {scope:'independent_paired',stage:'confirm',method:'hip_graph',reference_id:'cand_previous',candidate_id:'cand_new',reference_median_us:293,candidate_median_us:292},
    {scope:'independent_paired',stage:'final',method:'hip_graph',reference_id:'original',candidate_id:'cand_new',reference_median_us:314,candidate_median_us:292}]});
  assert.match(html,/原始 314 µs \/ 候选 292 µs/);
  assert.match(html,/参考 293 µs \/ 候选 292 µs/);
  assert.match(html,/cand_previous/);
  assert.ok(html.indexOf('原始 314') < html.indexOf('确认阶段配对记录'));
  assert.ok(html.indexOf('参考 293') > html.indexOf('确认阶段配对记录'));
});
test('independent diagnostic displays progress and escapes remote values', () => {
  const html = view.diagnostic({id:'moe-control',status:'running',scope:'diagnostic_only',
    records_completed:3,directory:'/remote/<script>',summary_path:null});
  assert.match(html, /独立诊断不计入候选采用或 \.co 完成数/);
  assert.match(html, /已完成记录 3/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.equal(view.diagnostic(null), '');
});

test('local original evidence displays times without inventing correctness or adoption', () => {
  const html = view.diagnostic({id:'original-v1', local_evidence:{status:'available', records:[
    {name:'original',repeat:0,compiled:true,correct:null,times_us:{hip_graph:243.1},sha256:'abc'}]}});
  assert.match(html, /本机诊断证据 · 1 条结果/);
  assert.match(html, /正确性 —/);
  assert.match(html, /243.1/);
  assert.doesNotMatch(html, /正确性 false/);
});
test('engine original batch exposes correct sample graph and op_test ranges', () => {
  const html = view.metrics({original_screen:{measurement:{status:'measured',correct:true,samples:[
    {result:{correct:true,time_us:6.1,detail:{runner:{op_test:{rows:[{'asm us':6.7}]}}}}},
    {result:{correct:false,time_us:1,detail:{}}}
  ]}}});
  assert.match(html, /正确样本 1 \/ 2/);
  assert.match(html, /HIP graph：6.1–6.1/);
  assert.match(html, /op_test：6.7–6.7/);
});

test('best correct graph screen stays explicitly unconfirmed with all candidates in details', () => {
  const html = view.metrics({candidate_screens:[
    {candidate_id:'wrong', correct:false, hip_graph:{median_us:1}},
    {candidate_id:'missing', correct:true, hip_graph:{median_us:null}},
    {candidate_id:'zero', correct:true, hip_graph:{median_us:0}},
    {candidate_id:'slower', correct:true, hip_graph:{median_us:7}},
    {candidate_id:'best<script>', correct:true, valid_samples:3, hip_graph:{median_us:6.2}, op_test:{median_us:6.8}}
  ]});
  const summary = html.split('</div><details>')[0];
  assert.match(summary, /screening（未独立确认）/);
  assert.match(summary, /best&lt;script&gt;/);
  assert.match(summary, /HIP graph：6.2 µs/);
  assert.match(summary, /op_test：6.8 µs/);
  assert.match(summary, /有效样本 3；筛选值不代表已确认收益/);
  assert.doesNotMatch(summary, /wrong|slower|配对收益|<script>/);
  assert.match(html, /slower/);
});

test('multiple op_test distributions are labeled aggregate only in screening', () => {
  const methods = ['hip_graph', 'op_test:constant/constant', 'op_test:uniform/auto'];
  const html = view.metrics({original_screen:{measurement:{samples:[{result:{correct:true,time_us:6,
    detail:{runner:{op_test:{rows:[{data_init:'constant',scale_init:'constant','asm us':7},
      {data_init:'uniform',scale_init:'auto','asm us':8}]}}}}}]}},
    paired_results:methods.map(method => ({method, stage:'final', scope:'independent_paired', reference_id:'original', pairs:8}))});
  const summary = html.split('</div><details>')[0];
  assert.match(summary, /op_test（多分布 aggregate screen）：7–8 µs/);
  for (const method of methods) assert.ok(summary.includes('独立配对 · ' + method));
  assert.equal((summary.match(/独立配对 · /g) || []).length, 3);
});

test('fixed candidate cross checks preserve method verdicts without inventing search winners', () => {
  const value = {cross_shape_results: {
    hip_graph:{pairs:8,verdict:'inconclusive',reference_median_us:7,candidate_median_us:6.9,lower_ratio_bound:1.006},
    'op_test:constant/constant':{pairs:8,verdict:'confirmed_gain'},
    'op_test:uniform/auto':{pairs:8,verdict:'confirmed_gain'}}};
  const html = view.metrics(value);
  assert.match(html, /固定候选复测已完成；未独立搜索/);
  assert.match(html, /3 种方法（不代表独立搜索或整体胜出）/);
  assert.match(html, /判定 inconclusive/);
  assert.doesNotMatch(html.split('</div><details>')[0], /采用候选|配对收益/);
  const retained = view.metrics({...value, campaign_decision:'original_retained'});
  assert.match(retained, /最终：保留原始/);
});

test('full campaign page distinguishes attempts from completed validation and declares its stop condition', async () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const box = {innerHTML:'', querySelectorAll:() => []};
  const inputs = {value:'', checked:false, addEventListener:() => {}};
  const campaign = {campaign_id:'full', generated_at:new Date().toISOString(),
    remote_updated_at:new Date().toISOString(), deadline:null,
    stop_condition:'all_runnable_workloads_completed', sync:{connected:true},
    completion:{attempted_tasks:2,total_tasks:2,associations_finished:false},
    adapter_coverage:{source:'plan.json:adapter_blocked_reasons',count:2,
      reasons:{'a.co':'other contracts not adapted','b.co':'keep <original> reason'}},
    local_publication:{status:'watching',published:1,error_count:0,latest_commit:'abc123'},
    counts:{known:2,target_count:2,finished:1,remaining:1}, kernels:[]};
  const context = {document:{querySelector:selector => selector === '#campaignsBox' ? box : inputs},
    window:{FACKCampaignView:view, FACKWorkloadView:require('./workload_view.js')},
    location:{hash:''}, setInterval:() => {},
    fetch:async () => ({ok:true, json:async () => ({campaigns:[campaign],errors:[]})})};
  vm.runInNewContext(fs.readFileSync(require.resolve('./campaigns.js'), 'utf8'), context);
  await new Promise(setImmediate);
  assert.match(box.innerHTML, /全部可调优任务完成/);
  assert.match(box.innerHTML, /已尝试 2 \/ 2/);
  assert.match(box.innerHTML, /已完成 1；待完成 1/);
  assert.match(box.innerHTML, /已尝试不等于通过完成验收/);
  assert.doesNotMatch(box.innerHTML, /首个严格确认胜出/);
  assert.match(box.innerHTML, /适配覆盖原因 · 2 个 .co 原始记录/);
  assert.match(box.innerHTML, /keep &lt;original&gt; reason/);
  assert.match(box.innerHTML, /不表示全部未调优，也不与 CSV 覆盖数量合并/);
  assert.match(box.innerHTML, /成功 1；错误 0；最新 commit abc123/);
});
