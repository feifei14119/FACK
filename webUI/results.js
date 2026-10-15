(function (root) {
  "use strict";
  const workload = typeof module !== "undefined" && module.exports ? require('./workload_view.js') : root.FACKWorkloadView;
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const numeric = (v) => typeof v === "number" && Number.isFinite(v);
  const fmt = (v) => numeric(v) ? v.toLocaleString("en-US", { maximumFractionDigits: 4 }) : "—";
  const pct = (v) => numeric(v) ? (v > 0 ? "+" : "") + v.toFixed(2) + "%" : "—";
  const statuses = {
    final_recommended: "最终采用候选", original_retained: "保留原始代码",
    not_finalized: "待最终验证", screening_only: "仅筛选结果",
    comparison_only: "配对比较完成", self_comparison: "同代码流程自检",
    running: "比较进行中", failed: "比较失败", invalid: "证据校验失败",
    confirmed_gain: "已确认收益", regression: "回退", inconclusive: "未确认差异",
    validation_passed: "单次验证通过", validation_failed: "单次验证失败",
  };
  const kinds = { run: "调优任务", comparison: "独立配对比较", archive: "归档实测", screening: "旧版筛选", campaign: "远端调优结果", validation: "Client / op_test 验证" };
  const verdict = (s) => statuses[s] || s || "未记录";
  const tone = (s) => s === "confirmed_gain" || s === "final_recommended" ? "good"
    : ["regression", "failed", "invalid"].includes(s) ? "bad" : "";

  function matches(row, filters) {
    const t = row.target || {};
    const text = [t.client, t.gfx, t.co, t.symbol, row.title, row.source, workload.searchable(row.workload)].join(" ").toLowerCase();
    return (!filters.client || t.client === filters.client) && (!filters.gfx || t.gfx === filters.gfx)
      && (!filters.query || text.includes(filters.query.trim().toLowerCase()));
  }

  function card(r) {
    const t = r.target || {};
    let html = '<div class="result-heading"><div><span class="result-kind">' + esc(kinds[r.kind] || r.kind) + '</span>'
      + '<h4>' + esc(r.title) + '</h4></div><span class="result-status ' + tone(r.status) + '">'
      + esc(verdict(r.status)) + '</span></div>';
    html += '<dl class="result-target"><div><dt>Client</dt><dd>' + esc(t.client || "未记录") + '</dd></div>'
      + '<div><dt>GFX</dt><dd>' + esc(t.gfx || "未记录") + '</dd></div>'
      + '<div class="co-target"><dt>调优 .co</dt><dd>' + esc(t.co ? t.co.split(/\/hsa\/gfx[0-9a-f]+\//).pop().split('/').slice(-2).join('/') : "未记录 .co（输入可能为 .s）") + '</dd></div></dl>';
    html += workload.summary(r.workload);
    if (r.selected) html += '<p class="result-selection">最终选择：<strong>' + esc(r.selected) + '</strong></p>';
    if ((r.metrics || []).length) {
      html += '<div class="comparison-scroll" tabindex="0" role="region" aria-label="性能对比表，可横向滚动"><table class="comparison-table"><caption>基线与候选性能对比</caption>'
        + '<thead><tr><th scope="col">测量</th><th scope="col">基线中位数</th><th scope="col">候选中位数</th>'
        + '<th scope="col">配对提升</th><th scope="col">提升界限 / 区间</th><th scope="col">配对数</th><th scope="col">判定</th></tr></thead><tbody>';
      r.metrics.forEach((m) => {
        const bounds = numeric(m.lower_gain_pct) && numeric(m.upper_gain_pct)
          ? pct(m.lower_gain_pct) + " ～ " + pct(m.upper_gain_pct) : "—";
        html += '<tr><th scope="row">' + esc(m.label) + '</th><td>' + fmt(m.baseline) + ' <small>' + esc(m.unit) + '</small></td>'
          + '<td>' + fmt(m.candidate) + ' <small>' + esc(m.unit) + '</small></td><td class="' + tone(m.verdict) + '">' + pct(m.gain_pct) + '</td>'
          + '<td>' + bounds + '<small class="bound-label">' + esc(m.bounds_label) + '</small></td><td>' + fmt(m.pairs) + '</td>'
          + '<td class="' + tone(m.verdict) + '">' + esc(verdict(m.verdict)) + '</td></tr>';
      });
      html += '</tbody></table></div><p class="comparison-scroll-hint">← 左右滑动查看完整对比 →</p><p class="result-explanation">µs 越低越好，score 越高越好。提升来自逐对比值，可能不同于两列中位数的直接比值。</p>';
    } else {
      html += r.measurement && numeric(r.measurement.time_us) ? '<p>单次验证耗时：' + fmt(r.measurement.time_us) + ' µs</p>' : '<p class="empty-hint">暂无完整的最终性能对比。</p>';
    }
    if (r.screening && numeric(r.screening.best)) {
      html += '<p class="result-explanation">筛选最高 score：' + fmt(r.screening.best) + '（仅供筛选参考）</p>';
    }
    if (r.screening && numeric(r.screening.baseline_time_us)) html += '<p class="result-explanation">原始筛选耗时：' + fmt(r.screening.baseline_time_us) + ' µs（不代表最终配对结果）</p>';
    html += (r.notes || []).map((note) => '<p class="result-note">' + esc(note) + '</p>').join("");
    html += '<details class="result-details artifact-details"><summary>产物路径信息与记录来源</summary><div>来源：<code>' + esc(r.source)
      + '</code></div>' + (t.symbol ? '<div>Symbol：<code>' + esc(t.symbol) + '</code></div>' : "")
      + (t.co ? '<div>原始 .co：<code>' + esc(t.co) + '</code></div>' : '')
      + (r.candidate ? '<div>被比较候选：<code>' + esc(r.candidate) + '</code></div>' : "")
      + (r.artifacts ? '<pre>' + esc(JSON.stringify(r.artifacts, null, 2)) + '</pre>' : '') + '</details>';
    return html;
  }

  const api = { card, matches };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FACKResults = api;
})(typeof window !== "undefined" ? window : globalThis);
