(function () {
  "use strict";
  const DOCS = window.TESTFT_DOCS;

  const $ = (sel, root) => (root || document).querySelector(sel);
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };
  const esc = (s) =>
    String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  // ---------- Hero ----------
  function renderHero() {
    const h = $("#hero");
    h.innerHTML =
      `<h1>${esc(DOCS.meta.title)}</h1>` +
      `<div class="sub">${esc(DOCS.meta.subtitle)}</div>` +
      `<div class="tagline">${esc(DOCS.meta.tagline)}</div>`;
  }

  // ---------- Nav ----------
  function renderNav() {
    const nav = $("#nav");
    DOCS.sections.forEach((s) => {
      const a = el("a", "nav-link");
      a.dataset.target = s.id;
      a.innerHTML = `<span class="nav-icon">${s.icon || "•"}</span><span>${esc(s.title)}</span>`;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const t = document.getElementById("sec-" + s.id);
        if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
        closeSidebar();
      });
      nav.appendChild(a);
    });
  }

  // ---------- Card renderers ----------
  function renderCode(card) {
    const wrap = el("div", "code-wrap");
    if (card.lang) wrap.appendChild(el("span", "code-lang", esc(card.lang)));
    const pre = el("pre", "code");
    const code = el("code");
    code.textContent = card.code;
    pre.appendChild(code);
    wrap.appendChild(pre);
    const btn = el("button", "copy-btn", "复制");
    btn.addEventListener("click", () => copy(card.code, btn));
    wrap.appendChild(btn);
    return wrap;
  }

  function renderTable(card) {
    const w = el("div", "tbl-wrap");
    const t = el("table", "tbl");
    const thead = el("thead");
    const htr = el("tr");
    card.columns.forEach((c) => htr.appendChild(el("th", null, esc(c))));
    thead.appendChild(htr);
    t.appendChild(thead);
    const tb = el("tbody");
    card.rows.forEach((r) => {
      const tr = el("tr");
      r.forEach((cell) => tr.appendChild(el("td", null, esc(cell))));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    w.appendChild(t);
    const box = el("div");
    box.appendChild(w);
    if (card.note) box.appendChild(el("div", "tbl-note", esc(card.note)));
    return box;
  }

  function renderFlow(card) {
    const ol = el("ol", "flow");
    card.steps.forEach((s) => ol.appendChild(el("li", null, esc(s))));
    return ol;
  }

  function buildCard(card) {
    // note & prose are their own block; others go inside a .card
    if (card.type === "note") {
      const n = el("div", "card note " + (card.tone || "info"));
      if (card.heading) n.appendChild(el("h3", null, esc(card.heading)));
      n.appendChild(el("div", null, card.html || ""));
      n.dataset.text = (card.heading || "") + " " + stripTags(card.html || "");
      return n;
    }

    const c = el("div", "card" + (card.type === "prose" ? " prose" : ""));
    if (card.heading) c.appendChild(el("h3", null, esc(card.heading)));
    if (card.desc) c.appendChild(el("div", "desc", esc(card.desc)));

    let bodyText = "";
    if (card.type === "cmd") {
      c.appendChild(renderCode(card));
      bodyText = card.code;
    } else if (card.type === "table") {
      c.appendChild(renderTable(card));
      bodyText = card.columns.join(" ") + " " + card.rows.map((r) => r.join(" ")).join(" ") + " " + (card.note || "");
    } else if (card.type === "flow") {
      c.appendChild(renderFlow(card));
      bodyText = card.steps.join(" ");
    } else if (card.type === "prose") {
      const d = el("div");
      d.innerHTML = card.html || "";
      c.appendChild(d);
      bodyText = stripTags(card.html || "");
    }
    c.dataset.text = (card.heading || "") + " " + (card.desc || "") + " " + bodyText;
    return c;
  }

  function stripTags(html) {
    const d = document.createElement("div");
    d.innerHTML = html;
    return d.textContent || "";
  }

  // ---------- Sections ----------
  function renderSections() {
    const root = $("#sections");
    DOCS.sections.forEach((s) => {
      const sec = el("section", "section");
      sec.id = "sec-" + s.id;
      const head = el("div", "section-head");
      head.innerHTML =
        `<h2><span class="sec-icon">${s.icon || "•"}</span>${esc(s.title)}</h2>` +
        (s.blurb ? `<p class="blurb">${esc(s.blurb)}</p>` : "");
      sec.appendChild(head);
      s.cards.forEach((card) => sec.appendChild(buildCard(card)));
      root.appendChild(sec);
    });
  }

  // ---------- Copy ----------
  function copy(text, btn) {
    const done = () => {
      if (btn) {
        btn.textContent = "已复制";
        btn.classList.add("done");
        setTimeout(() => {
          btn.textContent = "复制";
          btn.classList.remove("done");
        }, 1500);
      }
      showToast();
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    } else {
      fallbackCopy(text, done);
    }
  }
  function fallbackCopy(text, cb) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    cb && cb();
  }
  let toastTimer;
  function showToast() {
    const t = $("#toast");
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("show"), 1400);
  }

  // ---------- Search ----------
  function setupSearch() {
    const input = $("#searchInput");
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      let anyGlobal = false;
      DOCS.sections.forEach((s) => {
        const sec = document.getElementById("sec-" + s.id);
        const cards = sec.querySelectorAll(".card");
        let anyInSec = false;
        cards.forEach((c) => {
          const text = (c.dataset.text || "").toLowerCase();
          const match = !q || text.indexOf(q) !== -1;
          c.classList.toggle("hidden-search", !match);
          if (match) anyInSec = true;
        });
        const secMatch = !q || anyInSec || s.title.toLowerCase().indexOf(q) !== -1;
        sec.classList.toggle("hidden-search", !secMatch);
        if (secMatch) anyGlobal = true;
      });
      $("#noResults").hidden = anyGlobal;
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
      } else if (e.key === "Escape" && document.activeElement === input) {
        input.value = "";
        input.dispatchEvent(new Event("input"));
        input.blur();
      }
    });
  }

  // ---------- Scroll spy ----------
  function setupScrollSpy() {
    const links = document.querySelectorAll(".nav-link");
    const byId = {};
    links.forEach((l) => (byId[l.dataset.target] = l));
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            const id = en.target.id.replace("sec-", "");
            links.forEach((l) => l.classList.remove("active"));
            if (byId[id]) byId[id].classList.add("active");
          }
        });
      },
      { rootMargin: "-10% 0px -75% 0px", threshold: 0 }
    );
    DOCS.sections.forEach((s) => {
      const sec = document.getElementById("sec-" + s.id);
      if (sec) obs.observe(sec);
    });
  }

  // ---------- Sidebar (mobile) ----------
  function closeSidebar() { $("#sidebar").classList.remove("open"); }
  function setupSidebar() {
    $("#menuToggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
  }

  // ---------- LAN tip ----------
  function renderLanTip() {
    $("#lanTip").innerHTML = `本机访问地址：<code>${location.host || "localhost:8080"}</code>`;
  }

  // ---------- init ----------
  renderHero();
  renderNav();
  renderSections();
  setupSearch();
  setupScrollSpy();
  setupSidebar();
  renderLanTip();
})();
