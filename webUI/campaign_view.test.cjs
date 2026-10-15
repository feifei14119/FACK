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
