(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  const api = {
    async get(path) {
      const r = await fetch(path, { cache: "no-store" });
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
        pill.textContent = h.py38 ? "已连接 · python3.8 ✓" : "已连接 · 无 python3.8";
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
      if (t.dataset.tab === "results") { loadResults(); loadSkills(); }
    });
  });

  // ---------------- collect form params ----------------
  function collect(action) {
    const map = {
      tune: "#tuneForm", mine: "#mineForm",
      articulate: "#articulateForm", hw_validate: "#hwForm",
    };
    const sel = map[action];
    const p = {};
    if (!sel) return p;
    $$(sel + " [name]").forEach((el) => {
      if (el.type === "checkbox") p[el.name] = el.checked;
      else if (el.value !== "") p[el.name] = el.value;
    });
    return p;
  }

  // ---------------- run action ----------------
  async function runAction(action) {
    const params = collect(action);
    const res = await api.post("/api/run", { action, params });
    if (!res.ok) {
      toast(res.data.error || "启动失败", true);
      return;
    }
    toast("已启动：" + res.data.title);
    trackJob(res.data.id, true);
    refreshJobTabs();
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
  async function loadResults() {
    const box = $("#resultsBox");
    box.innerHTML = "加载中…";
    let data;
    try { data = await api.get("/api/results"); } catch (e) { box.innerHTML = '<span class="empty-hint">无法读取</span>'; return; }
    const rs = data.results || [];
    if (!rs.length) { box.innerHTML = '<span class="empty-hint">暂无结果（跑一次调优后这里会出现最好/最坏 kernel 汇总）。</span>'; return; }
    box.innerHTML = "";
    rs.forEach((r) => box.appendChild(resultCard(r)));
  }

  function resultCard(r) {
    const el = document.createElement("div");
    el.className = "result-item";
    const best = r.best || {};
    const worst = r.worst || {};
    const impPct = best.improvement != null ? (best.improvement * 100) : null;
    let html = '<div class="r-file">' + esc(r._file || "") + "</div>";
    html += '<div class="result-grid">';
    html += metric("筛选最高 TFLOPS", best.tflops, "good");
    html += metric("baseline", best.baseline_tflops != null ? best.baseline_tflops : worst.baseline_tflops, "");
    html += metric("最差 TFLOPS", worst.tflops, "");
    if (impPct != null) html += metric("筛选提升 %", impPct, impPct >= 0 ? "good" : "bad");
    if (r.evals_total != null) html += metric("评测 (正确/总)", (r.evals_correct != null ? r.evals_correct : "?") + " / " + r.evals_total, "");
    if (best.region) html += metric("区域", best.region, "");
    html += "</div>";
    html += '<div class="r-file">筛选结果，尚未独立复测确认。</div>';
    if (r.best_shader) html += '<div class="r-file" style="margin-top:8px">待复测 .s: ' + esc(r.best_shader) + "</div>";
    el.innerHTML = html;
    return el;
  }

  function metric(k, v, cls) {
    if (v == null) return "";
    let val = typeof v === "number" ? (Math.round(v * 1000) / 1000) : v;
    return '<div class="metric"><div class="k">' + esc(k) + '</div><div class="v ' + cls + '">' + esc(val) + "</div></div>";
  }

  async function loadSkills() {
    const box = $("#skillsBox");
    box.innerHTML = "加载中…";
    let data;
    try { data = await api.get("/api/skills"); } catch (e) { box.innerHTML = '<span class="empty-hint">无法读取</span>'; return; }
    const s = data.skills || {};
    box.innerHTML = "";
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
  // 若已有历史作业, 定期刷新一次标签
  setInterval(() => { if (!poller) refreshJobTabs(); }, 5000);
})();
