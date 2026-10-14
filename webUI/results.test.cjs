const test = require('node:test');
const assert = require('node:assert/strict');
const { card, matches } = require('./results.js');

test('identity and notes are escaped; retained original stays distinct from gain', () => {
  const html = card({ title: '<img src=x onerror=alert(1)>', kind: 'run', status: 'original_retained',
    selected: 'original', source: 'a.json', target: {client:'aiter',gfx:'gfx942',co:'a<bad>.co'},
    notes:['<script>oops</script>'], metrics:[{label:'HIP graph',unit:'µs',baseline:10,candidate:9,gain_pct:10,verdict:'inconclusive'}] });
  assert.ok(!html.includes('<img'));
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('a&lt;bad&gt;.co'));
  assert.ok(html.includes('保留原始代码'));
  assert.ok(html.includes('未确认差异'));
  assert.ok(!html.includes('class="good"'));
});

test('missing final data is not presented as zero improvement', () => {
  const html = card({title:'unfinished',kind:'run',status:'not_finalized',target:{},metrics:[]});
  assert.ok(html.includes('暂无完整的最终性能对比'));
  assert.ok(!html.includes('0.00%'));
});

test('client, gfx and code object filters combine', () => {
  const row={title:'run 1',target:{client:'aiter/hsa/gfx942',gfx:'gfx942',co:'dir/FP8.co'}};
  assert.ok(matches(row,{client:'aiter/hsa/gfx942',gfx:'gfx942',query:'fp8.co'}));
  assert.ok(!matches(row,{client:'other',query:''}));
  assert.ok(!matches(row,{gfx:'gfx950',query:'FP8'}));
  assert.ok(!matches(row,{query:'missing.co'}));
});
