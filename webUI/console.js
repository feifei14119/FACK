(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  const api = {
    async get(path) {
      const r = await fetch(path, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    },
    async post(path, body) {
      const r = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      return { ok: r.ok, data: await r.json() };
    },
  };

  // ---------------- toast ----------------
  let toastTimer;
  function toast(msg, err) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.toggle("err", !!err);
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
  }

  // ---------------- health + defaults ----------------
  async function initHealth() {
    try {
      const h = await api.get("/api/health");
      const pill = $("#health");
      if (h.ok) {
        pill.textContent = h.py38 ? "已连接 · python3.8" : "已连接 · python3";
        pill.classList.add("ok");
      }
    } catch (e) {
      $("#health").textContent = "后端未连接";
      $("#health").classList.add("bad");
    }
  }
  async function initDefaults() {
    try {
      const d = await api.get("/api/defaults");
      $$("[data-def]").forEach((inp) => {
        const k = inp.getAttribute("data-def");
        if (d[k] != null && !inp.value) inp.value = d[k];
      });
    } catch (e) {}
  }

  // ---------------- tabs ----------------
  $$(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.remove("active"));
      $$(".tabpane").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      $("#pane-" + t.dataset.tab).classList.add("active");
      $(".layout").classList.toggle("results-active", ["results", "campaigns", "workloads"].includes(t.dataset.tab));
      history.replaceState(null, '', '#' + t.dataset.tab);
      if (t.dataset.tab === "results") { loadResults(); loadSkills(); }
    });
  });
  $$('[data-goto]').forEach(button => button.addEventListener('click', () => $('[data-tab="' + button.dataset.goto + '"]').click()));

  // ---------------- collect form params ----------------
  function collect(action) {
    const map = {
      tune: "#tuneForm", mine: "#mineForm",
      articulate: "#articulateForm", dispatch_plan: "#planForm", dispatch_prepare: "#taskForm",
      dispatch_validate: "#taskForm", dispatch_init: "#taskForm", dispatch_evaluate: "#compareForm",
      dispatch_compare: "#compareForm", dispatch_assess: "#assessForm", run_step: "#runForm",
    };
    const sel = map[action];
    const p = {};
    const plannedSdk = action === 'tune' && $('#sdkSourceMode').value === 'planned';
    if (action.startsWith('dispatch_') && action !== 'dispatch_plan' || plannedSdk || action === 'run_step') {
      const selected = window.FACKWorkflow && window.FACKWorkflow.selection();
      if (!selected && action !== 'run_step') throw new Error('请先选择可验证 workload');
      Object.assign(p, selected || {});
      $$('#taskForm [name]').forEach(el => { if (el.value !== '') p[el.name] = el.value; });
    }
    if (!sel) return p;
    $$(sel + " [name]").forEach((el) => {
      if (el.type === "checkbox") p[el.name] = el.checked;
      else if (el.value !== "") p[el.name] = el.value;
    });
    return p;
  }

  // ---------------- run action ----------------
  async function runAction(action) {
    try {
    const params = collect(action);
    const res = await api.post("/api/run", { action, params });
    if (!res.ok) {
      toast(res.data.error || "启动失败", true);
      return;
    }
    toast("已启动：" + res.data.title);
    trackJob(res.data.id, true);
    refreshJobTabs();
    } catch (error) { toast(error.message || '操作失败', true); }
  }

  $$("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => runAction(btn.dataset.action));
  });

  // ---------------- job monitor ----------------
  const jobs = {};        // id -> {offset, status, title, ...}
  let activeJob = null;
  let follow = true;
  let poller = null;

  function setFoot(job) {
    const foot = $("#monitorFoot");
    if (!job) { foot.textContent = ""; return; }
    let cls = "rc-run", txt = "运行中…";
    if (job.status === "done") { cls = "rc-ok"; txt = "完成 (rc=0)"; }
    else if (job.status === "failed") { cls = "rc-bad"; txt = "失败 (rc=" + job.returncode + ")"; }
    else if (job.status === "stopped") { cls = "rc-bad"; txt = "已停止"; }
    foot.innerHTML =
      '<span class="' + cls + '">● ' + txt + "</span>  ·  用时 " + job.elapsed + "s  ·  " +
      '<span title="' + escAttr(job.cmd) + '">' + esc(job.title) + "</span>";
    $("#stopBtn").disabled = !(job.status === "running" || job.status === "starting");
  }

  function esc(s) { return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
  function escAttr(s) { return esc(s).replace(/"/g, "&quot;"); }

  async function trackJob(id, makeActive) {
    if (!jobs[id]) jobs[id] = { offset: 0, log: "" };
    if (makeActive) {
      activeJob = id;
      jobs[id].log = "";
      jobs[id].offset = 0;
      $("#logView").textContent = "";
    }
    startPolling();
  }

  function startPolling() {
    if (poller) return;
    poller = setInterval(pollActive, 1000);
    pollActive();
  }

  async function pollActive() {
    if (!activeJob) return;
    const j = jobs[activeJob];
    let data;
    try {
      data = await api.get("/api/job?id=" + activeJob + "&offset=" + (j.offset || 0));
    } catch (e) { return; }
    if (data.error) return;
    if (data.log) {
      j.log = (j.log || "") + data.log;
      j.offset = data.offset;
      const lv = $("#logView");
      lv.textContent = j.log;
      if (follow) lv.scrollTop = lv.scrollHeight;
    }
    j.status = data.status;
    j.title = data.title;
    j.returncode = data.returncode;
    j.elapsed = data.elapsed;
    j.cmd = data.cmd;
    setFoot(data);
    refreshJobTabsStatus();
    const finished = data.status === "done" || data.status === "failed" || data.status === "stopped";
    if (finished) {
      if (!j.notified && data.status === 'done' && window.FACKWorkflow) window.FACKWorkflow.refresh();
      j.notified = true;
      // 若没有任何运行中的作业, 停止轮询
      const anyRunning = Object.values(jobs).some((x) => x.status === "running" || x.status === "starting");
      if (!anyRunning) { clearInterval(poller); poller = null; }
    }
  }

  async function refreshJobTabs() {
    let data;
    try { data = await api.get("/api/jobs"); } catch (e) { return; }
    const box = $("#jobTabs");
    box.innerHTML = "";
    (data.jobs || []).slice(0, 12).forEach((j) => {
      if (!jobs[j.id]) jobs[j.id] = { offset: 0, log: "" };
      jobs[j.id].status = j.status;
      jobs[j.id].title = j.title;
      const el = document.createElement("div");
      el.className = "job-tab " + j.status + (j.id === activeJob ? " active" : "");
      el.innerHTML = '<span class="dot"></span>' + esc(shortTitle(j));
      el.title = j.cmd;
      el.addEventListener("click", () => switchJob(j.id));
      box.appendChild(el);
    });
    if (!activeJob && data.jobs && data.jobs.length) switchJob(data.jobs[0].id);
  }

  function refreshJobTabsStatus() {
    $$(".job-tab").forEach((el) => {});
    // 简单起见, 状态由下次 refreshJobTabs 更新; 这里只更新 active 高亮
  }

  function shortTitle(j) {
    const t = j.title || j.action;
    return t.length > 22 ? t.slice(0, 21) + "…" : t;
  }

  async function switchJob(id) {
    activeJob = id;
    if (!jobs[id]) jobs[id] = { offset: 0, log: "" };
    // 重新从头拉全量日志
    jobs[id].offset = 0;
    jobs[id].log = "";
    $("#logView").textContent = "加载中…";
    $$(".job-tab").forEach((el) => el.classList.remove("active"));
    try {
      const data = await api.get("/api/job?id=" + id + "&offset=0");
      jobs[id].log = data.log || "";
      jobs[id].offset = data.offset || 0;
      jobs[id].status = data.status;
      $("#logView").textContent = jobs[id].log || "(无输出)";
      $("#logView").scrollTop = $("#logView").scrollHeight;
      setFoot(data);
    } catch (e) {}
    startPolling();
    refreshJobTabs();
  }

  $("#stopBtn").addEventListener("click", async () => {
    if (!activeJob) return;
    await api.post("/api/stop", { id: activeJob });
    toast("已发送停止信号");
  });

  $("#autoscrollBtn").addEventListener("click", (e) => {
    follow = !follow;
    e.currentTarget.style.opacity = follow ? "1" : ".5";
    if (follow) { const lv = $("#logView"); lv.scrollTop = lv.scrollHeight; }
  });

  // ---------------- results ----------------
  let resultRows = [];
  function renderResults() {
    const filters = { client: $("#resultClient").value, gfx: $("#resultGfx").value, query: $("#resultQuery").value };
    const visible = resultRows.filter((r) => window.FACKResults.matches(r, filters));
    $("#resultsCount").textContent = "显示 " + visible.length + " / " + resultRows.length + " 条记录";
    $("#resultsBox").innerHTML = visible.length
      ? visible.map((r) => '<article class="result-item">' + window.FACKResults.card(r) + '</article>').join("")
      : '<p class="empty-hint">' + (resultRows.length ? "没有符合筛选条件的记录。" : "暂无调优记录。完成调优或配对比较后，点击刷新查看。") + '</p>';
  }

  function fillResultFilter(selector, key, label) {
    const select = $(selector), current = select.value;
    const options = [...new Set(resultRows.map((r) => (r.target || {})[key]).filter(Boolean))].sort();
    select.replaceChildren(new Option(label, ""), ...options.map((v) => new Option(v, v)));
    if (options.includes(current)) select.value = current;
  }

  async function loadResults() {
    const box = $("#resultsBox");
    $("#refreshResults").disabled = true;
    box.textContent = "加载中…";
    $("#resultsErrors").textContent = "";
    try {
      const data = await api.get("/api/results");
      if (!Array.isArray(data.results)) throw new Error("结果接口格式错误");
      resultRows = data.results;
      fillResultFilter("#resultClient", "client", "全部 client");
      fillResultFilter("#resultGfx", "gfx", "全部架构");
      $("#resultsErrors").textContent = (data.errors || []).map((e) => "暂无法读取 " + e.source + "：" + e.error).join("\n");
      renderResults();
    } catch (e) {
      box.textContent = "无法读取结果：" + e.message + "。请点击刷新重试。";
      $("#resultsCount").textContent = "";
    } finally {
      $("#refreshResults").disabled = false;
    }
  }

  ["#resultClient", "#resultGfx"].forEach((sel) => $(sel).addEventListener("change", renderResults));
  $("#resultQuery").addEventListener("input", renderResults);

  async function loadSkills() {
    const box = $("#skillsBox");
    box.innerHTML = "加载中…";
    let data;
    try { data = await api.get("/api/skills"); } catch (e) { box.innerHTML = '<span class="empty-hint">无法读取</span>'; return; }
    const s = data.skills || {};
    box.innerHTML = "";
    box.appendChild(skillGroup("Agent skills · 操作与验证", s.agent || []));
    box.appendChild(skillGroup("策展库 knowledge/engine/skills", s.store || []));
    box.appendChild(skillGroup("挖掘产出 study_out/skills", s.study || []));
  }
  function skillGroup(label, names) {
    const g = document.createElement("div");
    g.className = "skill-group";
    let html = '<div class="g-label">' + esc(label) + " (" + names.length + ")</div>";
    if (!names.length) html += '<span class="empty-hint">（空）</span>';
    else html += names.map((n) => '<span class="skill-chip">' + esc(n) + "</span>").join("");
    g.innerHTML = html;
    return g;
  }

  $("#refreshResults").addEventListener("click", loadResults);
  $("#refreshSkills").addEventListener("click", loadSkills);

  // ---------------- init ----------------
  initHealth();
  initDefaults();
  refreshJobTabs();
  const initialTab = $$('.tab').find(t => '#' + t.dataset.tab === location.hash);
  if (initialTab) initialTab.click();
  // 若已有历史作业, 定期刷新一次标签
  setInterval(() => { if (!poller) refreshJobTabs(); }, 5000);
})();
