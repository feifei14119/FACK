const test = require('node:test');
const assert = require('node:assert/strict');
const view = require('./workload_view.js');
const results = require('./results.js');

test('dimensions, CSV path and line are visible outside collapsed artifact info', () => {
  const workload = {inputs:{m:192,n:1280,k:1024,splitK:1},csv:[{path:'aiter/configs/test.csv',line:5}]};
  const html = results.card({title:'test',target:{co:'test.co'},workload,metrics:[],source:'/outputs/a.json'});
  assert.match(html,/M=192 · N=1280 · K=1024/);
  assert.match(html,/aiter\/configs\/test.csv/);
  assert.match(html,/第 5 行/);
  assert.match(html,/<details class="result-details artifact-details"><summary>产物路径信息/);
  assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
  assert.ok(results.matches({workload},{query:'1280'}));
  assert.ok(results.matches({workload},{query:'test.csv'}));
});

test('same co workload IDs remain separate and unsupported metadata is not invented', () => {
  assert.notEqual(view.key({co:'same.co',workload:{id:'shape-a'}}),view.key({co:'same.co',workload:{id:'shape-b'}}));
  assert.match(view.summary({inputs:{token:4,expert:8,topk:2}}),/token=4 · expert=8 · topk=2/);
  assert.match(view.summary({inputs:{m:192}}),/未记录 CSV 文件及行号/);
});

test('CSV and artifact strings are escaped and artifact paths are initially collapsed', () => {
  assert.doesNotMatch(view.summary({inputs:{m:'<script>'},csv:[{path:'<img>',line:9}]}),/<script>|<img>/);
  const html = view.artifactDetails('/remote/<img>/selected.co','<bad>');
  assert.match(html,/&lt;img&gt;/);
  assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
});
