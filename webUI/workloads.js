(function () {
  "use strict";
  const view = window.FACKWorkloadView;
  const $ = (id) => document.getElementById(id);
  let plans = [], selectedPlan = null, selected = null, page = 0;
  const pageSize = 40;
  const options = (select, rows, current) => {
    select.replaceChildren(...rows.map(r => new Option(r.label, r.value)));
    if (rows.some(r => r.value === current)) select.value = current;
  };
  function updateSdk() {
    const planned = $('sdkSourceMode').value === 'planned';
    document.querySelector('#tuneForm [data-action="tune"]').disabled = planned && !selected;
    for (const name of ['seed', 'client', 'params']) {
      document.querySelector('#tuneForm [name="' + name + '"]').readOnly = planned;
    }
    if (planned) {
      document.querySelector('#tuneForm [name="client"]').value = 'aiter/hsa/gfx942';
      document.querySelector('#tuneForm [name="seed"]').value = selected ? selected.seed : '';
      document.querySelector('#tuneForm [name="params"]').value = selected ?
        "--manifest '" + selected.manifest.replace(/'/g, "'\\''") + "'" : '';
    }
  }
  function selectTask(id) {
    selected = selectedPlan && selectedPlan.rows.find(r => r.id === id && r.manifest);
    const html = selected ? '<p class="selected-target"><strong>aiter / ' + view.esc(selectedPlan.arch) + ' / ' +
      view.esc(selected.co.join(", ")) + '</strong><br><small>Workload ' + view.esc(selected.id) + '</small></p>' +
      view.summary(selected.workload, true) + view.artifactDetails('manifest：' + selected.manifest + '\nseed：' + selected.seed, 'selected-workload')
      : '<p class="empty-hint">尚未选择可验证 workload。生成或选择计划后继续；待适配记录不能直接执行。</p>';
    $('selectedWorkload').innerHTML = html;
    $('verifyWorkload').innerHTML = html;
    document.querySelectorAll('[data-action^="dispatch_"]').forEach(button => {
      if (button.dataset.action !== 'dispatch_plan') button.disabled = !selected;
    });
    updateSdk();
    if (selected) {
      $('taskSelect').value = selected.id;
      const runId = document.querySelector('#taskForm [name="run_id"]').value || 'dispatch-' + selected.id;
      $('runDirectory').value = 'client/aiter/tune_out/runs/' + runId;
    }
  }
  function selectPlan(id) {
    const previous = selected && selected.id;
    selectedPlan = plans.find(p => p.id === id) || null;
    const ready = selectedPlan ? selectedPlan.rows.filter(r => r.manifest) : [];
    options($('taskSelect'), ready.length ? ready.map(r => ({value:r.id, label:r.family + ' · ' + view.shape(r.workload) + ' · ' + r.co.join(', ')})) :
      [{value:'',label:'该计划暂无可验证 workload'}], previous);
    selectTask($('taskSelect').value);
  }
  function render() {
    const plan = plans.find(p => p.id === $('browsePlan').value);
    if (!plan) {
      $('workloadsBox').innerHTML = '<p class="empty-hint">没有 dispatch 计划。展开下方表单生成新计划。</p>';
      $('workloadCounts').textContent = '';
      $('workloadPage').textContent = '';
      $('workloadPrev').disabled = $('workloadNext').disabled = true;
      return;
    }
    const query = $('workloadQuery').value.toLowerCase().trim(), status = $('workloadStatus').value;
    const rows = plan.rows.filter(r => (!status || r.status === status) && (!query ||
      [r.family,r.id,r.co.join(' '),r.symbol,r.backend,view.searchable(r.workload)].join(' ').toLowerCase().includes(query)));
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    page = Math.min(page, pages - 1);
    $('workloadCounts').textContent = plan.arch + ' / ' + plan.cu_num + ' CU · ' + plan.co_count + ' 个关联 .co · ' +
      plan.tasks + ' 个可验证 workload · 筛选 ' + rows.length + ' / ' + plan.rows.length + ' 条引用';
    $('workloadPage').textContent = '第 ' + (page + 1) + ' / ' + pages + ' 页';
    $('workloadPrev').disabled = page === 0; $('workloadNext').disabled = page + 1 >= pages;
    $('workloadsBox').innerHTML = '<div class="comparison-scroll"><table class="workload-table"><thead><tr><th>.co / backend</th><th>计划尺寸与 CSV 来源</th><th>状态 / 操作</th></tr></thead><tbody>' +
      rows.slice(page * pageSize, (page + 1) * pageSize).map(r => '<tr><td><strong>' + view.esc(r.family) + '</strong><br><code>' +
        view.esc(r.co.join(', ') || r.symbol || '未匹配 HSA') + '</code><p>' + view.esc(r.backend) + ' · ' + view.esc(r.stage) + '</p></td><td>' +
        view.summary(r.workload, true) + '</td><td><strong>' + view.esc(r.manifest ? '适配就绪，可验证' : view.status(r.status)) + '</strong><p>执行：' + view.esc(view.status((r.progress || {}).status)) + '</p><p class="desc">' + view.esc(r.reason) + '</p>' +
        (r.manifest ? '<button class="btn tiny" data-select-workload="' + view.esc(r.id) + '">选择此 workload</button>' +
          view.artifactDetails('manifest：' + r.manifest + '\nseed：' + r.seed, r.id) : '') + '</td></tr>').join('') + '</tbody></table></div>' +
      (rows.length ? '' : '<p class="empty-hint">没有符合筛选条件的引用。</p>') +
      '<details class="unreferenced-co"><summary>未找到配置引用的 .co · ' + (plan.unreferenced_co || []).length + ' 个</summary><p class="desc">只表示本计划的来源、gfx 和 CU 范围内未找到引用。MLA 等需要补充完整 workload。</p><ul>' +
      (plan.unreferenced_co || []).map(r => '<li><code>' + view.esc(r.co) + '</code> · ' + view.esc(r.reason) + '</li>').join('') + '</ul></details>';
    $('workloadsBox').querySelectorAll('[data-select-workload]').forEach(button => button.addEventListener('click', () => {
      $('planSelect').value = plan.id;
      selectPlan(plan.id); selectTask(button.dataset.selectWorkload);
      document.querySelector('[data-tab="tune"]').click();
    }));
  }
  async function refresh() {
    $('refreshWorkloads').disabled = true;
    try {
      const response = await fetch('/api/workloads', {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      plans = data.plans;
      const choices = plans.length ? plans.map(p => ({value:p.id,label:p.name + ' · ' + p.arch + '/' + p.cu_num + ' CU'})) : [{value:'',label:'暂无计划'}];
      options($('planSelect'), choices, $('planSelect').value);
      options($('browsePlan'), choices, $('browsePlan').value);
      $('workloadErrors').textContent = (data.errors || []).map(e => e.source + '：' + e.error).join('\n');
      selectPlan($('planSelect').value); render();
    } catch (e) { $('workloadErrors').textContent = '计划读取失败：' + e.message; }
    finally { $('refreshWorkloads').disabled = false; }
  }
  $('planSelect').addEventListener('change', () => selectPlan($('planSelect').value));
  $('sdkSourceMode').addEventListener('change', updateSdk);
  $('taskSelect').addEventListener('change', () => selectTask($('taskSelect').value));
  ['browsePlan','workloadQuery','workloadStatus'].forEach(id => $(id).addEventListener('input', () => {page=0;render();}));
  $('workloadPrev').addEventListener('click', () => {page--;render();});
  $('workloadNext').addEventListener('click', () => {page++;render();});
  $('refreshWorkloads').addEventListener('click', refresh);
  document.querySelector('#taskForm [name="run_id"]').addEventListener('input', e => {
    if (selected) $('runDirectory').value = 'client/aiter/tune_out/runs/' + (e.target.value || 'dispatch-' + selected.id);
  });
  window.FACKWorkflow = {refresh, selection: () => selected ? {plan:selectedPlan.id, task_id:selected.id} : null};
  selectTask(null); refresh();
})();
