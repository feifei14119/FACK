(function () {
  "use strict";
  const box = document.querySelector("#campaignsBox");
  if (!box) return;
  const esc = (value) => String(value == null ? "—" : value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const date = (value) => value ? new Date(value).toLocaleString("zh-CN", {hour12: false}) : "尚未收到";
  let records = [];
  let errors = [];
  const filters = ["campaignQuery", "campaignPending"];

  function render() {
    const expanded = new Set(Array.from(box.querySelectorAll('details[data-detail-key][open]')).map(d => d.dataset.detailKey));
    const query = document.querySelector("#campaignQuery").value.toLowerCase().trim();
    const onlyPending = document.querySelector("#campaignPending").checked;
    box.innerHTML = errors.map((e) => '<p class="campaign-error">' + esc(e.error || e) + '</p>').join("") +
      records.map((campaign) => {
        const count = campaign.counts || {};
        const sync = campaign.sync || {};
        const age = Math.max(0, (Date.now() - Date.parse(campaign.generated_at)) / 1000);
        const remoteAge = Math.max(0, (Date.now() - Date.parse(campaign.remote_updated_at)) / 1000);
        const dead = Date.now() >= Date.parse(campaign.deadline);
        const stopped = campaign.monitor_status === "finished";
        const warning = !sync.connected ? "远端通信失败 · 以下为最后同步记录" :
          age > 180 && !stopped ? "本机监控未更新 · 检查后台进程" :
          Object.keys(sync.errors || {}).length ? "已连接 · 部分状态文件尚未同步" : "远端已连接";
        const pending = new Set((campaign.remaining || []).map(window.FACKWorkloadView.key));
        const rows = (campaign.kernels || []).filter((r) => (!onlyPending || pending.has(window.FACKWorkloadView.key(r))) &&
          (!query || JSON.stringify(r).toLowerCase().includes(query)));
        const local = campaign.local_exports || {};
        const localFiles = local.status === 'verified' ? local.files || [] : [];
        const ratio = count.target_count ? Math.min(100, 100 * count.finished / count.target_count) : 0;
        return '<article class="card campaign-card"><h3>' + esc(campaign.campaign_id) + '</h3>' +
          '<p class="campaign-connection ' + (!sync.connected || (age > 180 && !stopped) ? 'campaign-error' : '') + '">' + esc(warning) +
          ' · ' + (stopped ? '周期监控已结束' : dead ? '已到截止时间，正在收尾同步' : '周期监控运行中') + '</p>' +
          (remoteAge > 180 && !stopped ? '<p class="campaign-error">远端进度已有 ' + Math.floor(remoteAge / 60) +
            ' 分钟未更新；以下仍为该时间戳的记录。</p>' : '') +
          '<dl class="campaign-meta"><div><dt>阶段 / 远端状态</dt><dd>' + esc(campaign.phase) + ' / ' + esc(campaign.status) + '</dd></div>' +
          '<div><dt>当前步骤</dt><dd>' + esc(campaign.active_step) + '</dd></div>' +
          '<div><dt>当前 .co</dt><dd>' + esc(campaign.current_co) + '</dd></div>' +
          '<div><dt>本机同步尝试</dt><dd>' + esc(date(sync.attempted_at)) + '</dd></div>' +
          '<div><dt>最近成功通信</dt><dd>' + esc(date(sync.last_success_at)) + '</dd></div>' +
          '<div><dt>远端状态更新时间</dt><dd>' + esc(date(campaign.remote_updated_at)) + '</dd></div>' +
          '<div><dt>硬截止（本机时区）</dt><dd>' + esc(date(campaign.deadline)) + '</dd></div></dl>' +
          '<p>GPU 停止核验：<strong>' + esc((campaign.gpu_stop || {}).status || 'not_checked') + '</strong></p>' +
          window.FACKCampaignView.diagnostic(campaign.diagnostic) +
          '<p>已知 <strong>' + esc(count.known) + '</strong> 个 .co；本次范围 <strong>' + esc(count.target_count) +
          '</strong>；范围外 ' + esc(count.out_of_scope) + '；已完成 ' + esc(count.finished) + '；待完成 ' + esc(count.remaining) + '</p>' +
          '<p class="desc">类别：' + esc(JSON.stringify(campaign.category_counts || {})) + '</p>' +
          (localFiles.length ? '<details class="campaign-local-exports artifact-details" data-detail-key="exports-' + esc(campaign.campaign_id) + '"><summary>产物路径信息 · 本机确认产物 · ' + localFiles.length +
            ' 个文件已核验 SHA256</summary><ul>' + localFiles.map((file) => '<li><a href="/api/campaign/export?campaign=' +
              encodeURIComponent(campaign.campaign_id) + '&amp;file=' + encodeURIComponent(file.path) + '">下载 ' + esc(file.path) +
              '</a><br><small>本机：' + esc(file.local_path) + '<br>SHA256：' + esc(file.sha256) + '</small></li>').join('') + '</ul></details>' :
            '<p class="desc">本机确认产物：' + esc(local.status === 'failed' ? '取回失败，详情见同步记录' : '尚无已取回的确认采用文件') + '</p>') +
          '<progress class="campaign-progress" max="100" value="' + ratio + '"></progress>' +
          '<p class="desc">完成数采用远端明确的完成状态；blocked、无实测待处理对象保留在待完成清单。结果阶段和测量原值逐项列出。</p>' +
          '<details><summary>同步详情、阶段截止与报告路径</summary><pre>' + esc(JSON.stringify({
            phase_deadlines: campaign.phase_deadlines, sync: sync, latest_report: campaign.latest_report,
            snapshot_path: campaign.snapshot_path, remote_output: campaign.remote_output,
            remote_counts: campaign.remote_counts, notes: campaign.notes, gpu_stop: campaign.gpu_stop,
            diagnostic_history: campaign.diagnostic_history,
            local_diagnostic_sync: campaign.local_diagnostic_sync,
            local_exports: campaign.local_exports || {status: '尚未取回；下表为远端产物'}
          }, null, 2)) + '</pre></details>' +
          '<p class="desc">显示 ' + rows.length + ' / ' + (campaign.kernels || []).length + ' 个已知 .co</p>' +
          '<div class="campaign-table-wrap"><table class="campaign-table"><thead><tr><th>.co / 类别</th><th>状态 / 结果阶段</th><th>原因</th><th>测试 workload / 实际性能</th><th>任务与产物</th></tr></thead><tbody>' +
          rows.map((r) => '<tr><td><code>' + esc(r.co) + '</code><br><small>' + esc(r.category) + '</small></td><td>' +
            esc(r.status) + '<br><small>' + esc(r.result_stage || r.phase || '') + '</small></td><td>' + esc(r.reason) +
            '</td><td>' + window.FACKWorkloadView.summary(r.workload) + window.FACKCampaignView.metrics(r.metrics) + '</td><td><code>' + esc(r.run_id) + '</code>' +
            window.FACKWorkloadView.artifactDetails(window.FACKCampaignView.artifacts(r, campaign), campaign.campaign_id + '-' + window.FACKWorkloadView.key(r)) + '</td></tr>').join("") +
          '</tbody></table></div>' + (rows.length ? '' : '<p class="desc">暂无符合条件的远端记录。尚未收到 inventory 时，数量 0 不代表没有 .co。</p>') + '</article>';
      }).join("") || '<p class="desc">尚无本机同步快照。监控程序生成 snapshot.json 后自动显示。</p>';
    box.querySelectorAll('details[data-detail-key]').forEach(d => { d.open = expanded.has(d.dataset.detailKey); });
  }
  async function refresh() {
    try {
      const response = await fetch("/api/campaigns", {cache: "no-store"});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      records = data.campaigns || [];
      errors = data.errors || [];
    } catch (error) {
      errors = [{error: "本机页面 API 读取失败；现有展示可能过期：" + error.message}];
    }
    render();
  }
  filters.forEach((id) => document.querySelector("#" + id).addEventListener("input", render));
  document.querySelector("#refreshCampaigns").addEventListener("click", refresh);
  refresh();
  setInterval(refresh, 15000);
  if (location.hash === "#campaigns") document.querySelector('[data-tab="campaigns"]').click();
})();
