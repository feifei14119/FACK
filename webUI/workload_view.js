(function (root) {
  "use strict";
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g,
    (c) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  const names = {ready_for_validation:"待原始验证", unsupported_adapter:"待适配 / 调查",
    other_backend:"其他 backend", unmapped:"未匹配 HSA", ambiguous_catalog:"目录匹配不唯一",
    missing_co:"缺少 .co", config_conflict:"配置冲突", not_checked:"尚未验证派发",
    verified:"正常入口派发已验证", failed:"派发验证失败", not_recorded:"未记录派发验证"};
  Object.assign(names, {not_started:"尚未开始", validation_passed:"单次验证通过", validation_failed:"单次验证失败",
    not_finalized:"调优中 / 待最终验证", comparison_only:"独立配对完成", final_recommended:"最终采用候选",
    original_retained:"保留原始代码", invalid:"证据校验失败"});
  const status = (v) => names[v] || v || "未记录";
  function shape(w) {
    const p = (w || {}).inputs || {};
    const dims = ["m", "n", "k"].map(k => p[k] == null ? p[k.toUpperCase()] : p[k]);
    if (dims.some(v => v != null)) return dims.map((v, i) => ["M", "N", "K"][i] + "=" + (v == null ? "未记录" : v)).join(" · ");
    const keys = ["token", "tokens", "model_dim", "inter_dim", "expert", "topk", "batch", "batch_size", "kv_len", "kv_seq_len", "q_seq_len", "num_heads"];
    const items = keys.filter(k => p[k] != null).map(k => k + "=" + p[k]);
    return items.join(" · ") || "未记录测试尺寸";
  }
  function summary(w, planned) {
    w = w || {};
    const p = w.inputs || {};
    let html = '<div class="workload-summary"><strong>' + (planned ? "计划尺寸：" : "测试尺寸：") + esc(shape(w)) + '</strong>';
    const attrs = ["splitK", "ksplit", "dtype", "outdtype", "bpreshuffle"].filter(k => p[k] != null)
      .map(k => k + "=" + p[k]);
    if (w.cu_num != null) attrs.unshift("CU=" + w.cu_num);
    if (attrs.length) html += '<div class="workload-attrs">' + esc(attrs.join(" · ")) + '</div>';
    html += '<div class="csv-source"><span>CSV 来源：</span>' + ((w.csv || []).length
      ? w.csv.map(s => '<code>' + esc(s.path) + '</code> <strong>第 ' + esc(s.line || "未记录") + ' 行</strong>').join('<br>')
      : '<span class="muted">未记录 CSV 文件及行号（不从当前配置补填）</span>') + '</div>';
    if (w.selection === "dispatch_csv") html += '<div class="workload-attrs">' + esc(status(w.dispatch_status)) + '</div>';
    html += (w.notes || []).map(s => '<p class="result-note">' + esc(s) + '</p>').join("");
    if (Object.keys(p).length) html += '<details class="workload-inputs"><summary>完整测试参数</summary><pre>' + esc(JSON.stringify(p, null, 2)) + '</pre></details>';
    return html + '</div>';
  }
  function searchable(w) {
    return [shape(w), (w || {}).id, JSON.stringify((w || {}).inputs || {}),
      ...((w || {}).csv || []).map(s => s.path + " " + s.line)].join(" ").toLowerCase();
  }
  const key = (r) => r.task_id || r.workload_id || (r.workload || {}).id || r.co || r.run_id;
  function artifactDetails(text, id) {
    return '<details class="artifact-details" data-detail-key="' + esc(id || "") + '"><summary>产物路径信息</summary><pre>' + esc(text) + '</pre></details>';
  }
  const api = {esc, status, shape, summary, searchable, key, artifactDetails};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FACKWorkloadView = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
