(function (root, factory) {
  const api = factory(typeof module === "object" && module.exports ? require('./workload_view.js') : root.FACKWorkloadView);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.FACKCampaignView = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (workload) {
  "use strict";
  const esc = (value) => String(value == null ? "—" : value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
  const number = (value) => typeof value === "number" && Number.isFinite(value) ?
    value.toLocaleString("en-US", {maximumFractionDigits: 5, useGrouping: false}) : "—";
  const identity = (value) => value ? '<code title="' + esc(value) + '">' +
    esc(value.length > 22 ? value.slice(0, 18) + '…' : value) + '</code>' : '未记录';
  function paired(row) {
    const reference = row.reference_id === 'original' ? '原始' : '参考';
    return '<p><strong>独立配对 · ' + esc(row.method) + '</strong><br><small>阶段 ' + esc(row.stage) +
      ' · ' + esc(row.pairs) + ' 对</small><br>' + reference + ' ' + number(row.reference_median_us) +
      ' µs / 候选 ' + number(row.candidate_median_us) + ' µs<br><small>' + reference + ' ID：' +
      identity(row.reference_id) + '<br>候选 ID：' + identity(row.candidate_id) +
      '</small><br>配对收益 ' + number(row.gain_pct) + (typeof row.gain_pct === 'number' ? '%' : '') +
      '<br><small>' + esc(row.verdict) + ' · 比值界限 [' + number(row.ratio_lower_bound) + ', ' +
      number(row.ratio_upper_bound) + ']</small></p>';
  }
  function metrics(value) {
    if (!value || !Object.keys(value).length) return '<span class="desc">尚无实测</span>';
    const screen = value.original_screen || {};
    const final = value.final || {};
    const invalid = value.valid_for_adoption === false;
    const decision = value.campaign_decision || final.status;
    const names = {original_retained: "保留原始", retained_original: "保留原始",
      candidate_adopted: "采用候选", candidate_selected: "采用候选", adopted: "采用候选",
      confirmed_gain: "采用候选", final_recommended: "候选获最终推荐"};
    let html = '<div class="campaign-metric-summary">';
    if (invalid) html += '<p class="campaign-error"><strong>候选验证失败，不可采用</strong><br>' +
      '后续静态审计未通过；历史配对结果不计为有效收益。审计记录见完整字段。</p>';
    if (screen.status === "measured" && screen.correct === true) {
      html += '<p><strong>原始筛选 · screening</strong><br>' + number(screen.time_us) + ' µs · ' +
        number(screen.tflops) + ' TFLOPS<br><small>有效样本 ' + esc(screen.valid_samples) + '</small></p>';
    } else if (Object.keys(screen).length) {
      html += '<p>原始筛选：' + esc(screen.status) + ' · 正确性 ' + esc(screen.correct) + '</p>';
    }
    html += '<p>候选：准备 ' + esc(value.prepared_candidates) + ' / 尝试 ' + esc(value.attempted_candidates) +
      ' / 有效实测 ' + esc(value.valid_measured_candidates) + '</p>';
    if (value.screened_candidates != null) html += '<p>已筛选 ' + esc(value.screened_candidates) + '</p>';
    const decisionText = decision === 'final_recommended' && value.valid_for_adoption === true ? '采用候选' :
      decision ? names[decision] || decision : '尚未决定';
    html += '<p><strong>最终：' + esc(invalid ? '候选验证失败，不可采用' : decisionText) + '</strong>' +
      (final.reason ? '<br><small>' + esc(final.reason) + '</small>' : '') + '</p>';
    const pairs = (invalid ? [] : Array.isArray(value.paired_results) ? value.paired_results : []).filter((row) => row &&
      (row.scope === 'independent_paired' || row.independent === true));
    if (!pairs.length && !invalid) html += '<p class="desc">尚无独立配对统计；未计算收益。</p>';
    pairs.filter((row) => row.stage === 'final').forEach((row) => { html += paired(row); });
    const earlier = pairs.filter((row) => row.stage !== 'final');
    if (earlier.length) html += '<details><summary>确认阶段配对记录 · ' + earlier.length +
      ' 项（参考可能为当时候选）</summary>' + earlier.map(paired).join('') + '</details>';
    html += '</div><details><summary>完整实测字段</summary><pre>' + esc(JSON.stringify(value, null, 2)) + '</pre></details>';
    return html;
  }

  function artifacts(row, campaign) {
    const hostRoot = campaign.remote_workspace;
    const containerRoot = campaign.container_workspace || '/workspace/FACK';
    const paths = Array.isArray(row.artifacts) ? row.artifacts.slice() : row.artifacts ? [row.artifacts] : [];
    const chosen = (row.metrics || {}).selected_artifact || {};
    if (chosen.assembly) paths.unshift({path: chosen.assembly, kind: '选择的汇编 .s', sha256: chosen.assembly_sha256});
    if (chosen.code_object) paths.unshift({path: chosen.code_object, kind: '选择的代码对象 .co', sha256: chosen.co_sha256});
    if (!paths.length) return '尚无远端产物';
    return paths.map((value) => {
      const path = typeof value === 'string' ? value : value.path;
      let host = null;
      if (path && hostRoot) {
        if (path.startsWith(containerRoot + '/')) host = hostRoot + path.slice(containerRoot.length);
        else if (!path.startsWith('/')) host = hostRoot + '/' + path;
        else if (path.startsWith(hostRoot + '/')) host = path;
      }
      return (value.kind ? value.kind + '\n' : '') + '远端记录路径：' + (path || JSON.stringify(value)) +
        '\n远端宿主路径：' + (host || '尚未映射') + (value.sha256 ? '\nSHA256：' + value.sha256 : '');
    }).join('\n\n');
  }
  function diagnostic(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || !Object.keys(value).length) return '';
    const local = value.local_evidence || {};
    const evidence = local.status === 'available' ? '<details open><summary>本机诊断证据 · ' +
      (local.records || []).length + ' 条结果</summary>' + (local.records || []).map((row) =>
        '<p><strong>' + esc(row.name) + ' · 第 ' + esc(row.repeat) + ' 次</strong><br>编译 ' + esc(row.compiled) +
        ' · 正确性 ' + esc(row.correct) + '<br>耗时（µs）：' + esc(JSON.stringify(row.times_us)) +
        '<br><small>SHA256：' + esc(row.sha256) + '</small></p>').join('') +
      '<details><summary>摘要、完整检查及本机路径</summary><pre>' + esc(JSON.stringify(local, null, 2)) +
      '</pre></details></details>' : '<p class="desc">本机诊断证据：' +
        esc(local.status === 'failed' ? '读取失败，详情见完整字段' : '尚未同步') + '</p>';
    return '<div class="campaign-diagnostic"><p><strong>独立诊断 · ' + esc(value.id) + '</strong><br>' +
      '状态 ' + esc(value.status) + ' · 范围 ' + esc(value.scope) + ' · 已完成记录 ' + esc(value.records_completed) +
      '</p><p class="desc">独立诊断不计入候选采用或 .co 完成数。</p>' +
      workload.artifactDetails('远端目录：' + (value.directory || '未记录') + '\n远端摘要：' + (value.summary_path || '未记录'), 'diagnostic-' + value.id) +
      evidence + '<details><summary>完整诊断字段</summary><pre>' + esc(JSON.stringify(value, null, 2)) +
      '</pre></details></div>';
  }
  return {metrics, artifacts, diagnostic};
});
