(() => {
  "use strict";

  const api = () => window.pywebview.api;
  const $ = (id) => document.getElementById(id);
  const FORMAT_EXTENSIONS = { bibtex: "bib", ris: "ris", csljson: "json", xlsx: "xlsx" };

  // ===== Idioma =====================================================================
  // Por defecto el del sistema; se recuerda en Ajustes (UI_LANGUAGE).

  let lang = (navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en";

  function t(key, vars) {
    let text = (I18N[lang] && I18N[lang][key]) ?? I18N.es[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) text = text.split(`{${k}}`).join(String(v));
    return text;
  }

  function fmtNum(n) {
    return Number(n || 0).toLocaleString(lang === "es" ? "es-ES" : "en-US");
  }

  function applyLanguage() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i]").forEach((el) => (el.textContent = t(el.dataset.i)));
    document.querySelectorAll("[data-i-ph]").forEach((el) => (el.placeholder = t(el.dataset.iPh)));
    document.querySelectorAll("[data-i-title]").forEach((el) => (el.title = t(el.dataset.iTitle)));
    document.querySelectorAll(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === lang));
    document.querySelectorAll("#settings-lang-seg button").forEach((b) => b.classList.toggle("on", b.dataset.value === lang));
    // Lo que se pinta con datos se vuelve a pintar en el idioma nuevo
    updateGenerationsHint();
    updateEstimate();
    renderQuota();
    if (currentRoot) renderRootPaper(currentRoot);
    if (lastResults.papers.length) renderResults();
    if (!screens["screen-curation"].classList.contains("hidden")) showCurationCard();
    if (!screens["screen-export"].classList.contains("hidden")) renderExportSummary();
  }

  async function setLanguage(newLang, persist = true) {
    lang = newLang === "en" ? "en" : "es";
    applyLanguage();
    if (persist) {
      try { await api().save_settings({ UI_LANGUAGE: lang }); } catch (err) { console.error(err); }
    }
  }

  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => setLanguage(b.dataset.lang)));

  // ===== Tema =========================================================================

  let theme = "system";
  function applyTheme() {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    document.querySelectorAll("#settings-theme-seg button").forEach((b) => b.classList.toggle("on", b.dataset.value === theme));
  }

  // ===== Cuota diaria de OpenAlex ===================================================
  // Sale de las cabeceras X-RateLimit de OpenAlex (via Python): no hay contador
  // propio que se desincronice ni que haya que reiniciar a mano.

  let lastQuota = { known: false };

  function fmtReset(seconds) {
    if (seconds == null) return t("resetUnknown");
    const m = Math.max(1, Math.round(seconds / 60)), h = Math.floor(m / 60);
    return h ? t("resetHM", { h, m: m % 60 }) : t("resetM", { m });
  }

  function renderQuota() {
    const chip = $("quota-chip");
    const q = lastQuota;
    chip.classList.toggle("hidden", !q.known);
    if (!q.known) return;
    const reset = fmtReset(q.reset_in);
    chip.classList.toggle("out", q.remaining <= 0);
    chip.classList.toggle("low", q.remaining > 0 && q.searches_left <= 2);
    chip.textContent = q.remaining <= 0 ? t("quotaOut", { reset })
      : q.searches_total ? t("quotaLeft", { n: q.searches_left, total: q.searches_total })
      : t("quotaLeftNoTotal", { n: q.searches_left });
    chip.title = t("quotaTitle", { limit: fmtNum(q.limit || 1000), remaining: fmtNum(q.remaining), reset });
  }

  async function refreshQuota() {
    try { lastQuota = await api().get_quota(); } catch (err) { console.error(err); }
    renderQuota();
  }

  // ===== Pantallas y pasos ===========================================================

  const screens = {};
  document.querySelectorAll(".screen").forEach((el) => (screens[el.id] = el));
  const STEP_OF = {
    "screen-input": 1, "screen-confirm": 1, "screen-params": 2, "screen-progress": 2,
    "screen-results": 3, "screen-curation": 4, "screen-export": 5, "screen-settings": 0,
  };
  let currentScreen = "screen-input";
  let screenBeforeSettings = "screen-input";

  function showScreen(id) {
    Object.values(screens).forEach((el) => el.classList.add("hidden"));
    screens[id].classList.remove("hidden");
    currentScreen = id;
    const step = STEP_OF[id];
    document.querySelectorAll(".step").forEach((el) => {
      const n = Number(el.dataset.step);
      el.classList.toggle("now", n === step);
      el.classList.toggle("done", step > 0 && n < step);
      el.classList.toggle("reachable", !!stepTarget(n) && id !== "screen-progress");
    });
    document.querySelector(".main").scrollTop = 0;
  }

  // ===== Navegacion (v3.1) =============================================================
  // Los pasos de la cabecera y el logo llevan a cualquier pantalla a la que ya se
  // puede ir; nada se pierde: los resultados siguen ahi hasta la siguiente busqueda.
  // Mientras busca no se navega (la busqueda sigue corriendo en Python).

  function stepTarget(n) {
    if (n === 1) return "screen-input";
    if (n === 2 && currentRoot) return "screen-params";
    if (n === 3 && lastResults.papers.length) return "screen-results";
    if (n === 5 && lastResults.papers.length) return "screen-export";
    return null; // la curacion se empieza desde resultados
  }

  function goHome() {
    if (currentScreen === "screen-progress") return;
    inputRaw.value = "";
    setError("input-error", "");
    showScreen("screen-input");
    inputRaw.focus();
  }

  document.querySelectorAll(".step").forEach((el) => el.addEventListener("click", () => {
    const target = stepTarget(Number(el.dataset.step));
    if (!target || currentScreen === "screen-progress" || target === currentScreen) return;
    if (target === "screen-input") goHome();
    else if (target === "screen-export") openExportScreen();
    else showScreen(target);
  }));

  $("brand-btn").addEventListener("click", goHome);

  // ===== Aviso al terminar (v3.1) =====================================================
  // Solo si la ventana no tiene el foco: si estas mirando, no hace falta avisar.

  let notifyOn = true;

  async function notifyIfAway(outcome, message) {
    if (!notifyOn || document.hasFocus()) return;
    try { await api().notify_search_done({ outcome, message: message || "", lang }); } catch (err) { console.error(err); }
  }

  // ===== Errores ======================================================================

  function humanWait(seconds) {
    if (seconds == null) return t("waitUnknown");
    if (seconds >= 5400) return t("waitHours", { n: Math.round(seconds / 3600) });
    if (seconds >= 3600) return t("waitHour");
    if (seconds >= 60) return t("waitMinutes", { n: Math.round(seconds / 60) });
    return t("waitSeconds", { n: Math.round(seconds) });
  }

  // El backend devuelve un `code` que se traduce aqui; en espanol, si no hay
  // texto propio para ese code, se muestra su mensaje detallado tal cual.
  function errorText(res) {
    if (!res) return t("errUnexpected");
    if (res.code === "rate_limited") return t("err_rate_limited", { source: res.source || "OpenAlex", wait: humanWait(res.wait_seconds) });
    if (lang === "es" && res.message) return res.message.charAt(0).toUpperCase() + res.message.slice(1);
    const key = `err_${res.code}`;
    return I18N[lang][key] || res.message || t("errUnexpected");
  }

  function unexpected(err) {
    console.error(err);
    return t("errUnexpected");
  }

  function setError(elId, message) {
    const el = $(elId);
    el.textContent = message || "";
    el.classList.toggle("hidden", !message);
  }

  // ===== Utilidades de pintado ===================================================

  function paperMeta(paper) {
    const authors = (paper.authors || []).slice(0, 3).join(", ") || t("unknownAuthors");
    const more = (paper.authors || []).length > 3 ? "…" : "";
    return `${authors}${more} · ${paper.year || t("noYear")}${paper.venue ? " · " + paper.venue : ""}`;
  }

  function accessLabel(paper) {
    const key = { open: "accOpen", open_bronze: "accBronze", institution: "accInst", none: "accNone" }[paper.access_status];
    return t(key || "accUnknown");
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  // ===== 1. Inicio ===================================================================

  const inputRaw = $("input-raw");

  async function doResolve(raw) {
    if (!raw || !raw.trim()) {
      setError("input-error", t("emptyInput"));
      return;
    }
    setError("input-error", "");
    showProgress(t("resolving"));
    try {
      const res = await api().resolve(raw.trim());
      refreshQuota();
      if (res.status === "resolved") showParamsScreen(res.paper);
      else if (res.status === "needs_confirmation") showConfirmScreen(res.query, res.candidates);
      else { showScreen("screen-input"); setError("input-error", errorText(res)); }
    } catch (err) {
      showScreen("screen-input");
      setError("input-error", unexpected(err));
    }
  }

  $("resolve-btn").addEventListener("click", () => doResolve(inputRaw.value));
  inputRaw.addEventListener("keydown", (e) => { if (e.key === "Enter") doResolve(inputRaw.value); });

  $("pick-pdf-btn").addEventListener("click", async () => {
    try {
      const path = await api().pick_pdf();
      if (path) { inputRaw.value = path; doResolve(path); }
    } catch (err) {
      setError("input-error", unexpected(err));
    }
  });

  // Soltar un PDF: el navegador no da la ruta a JS; la da pywebview a Python,
  // que llama aqui (ver _bind_pdf_drop en app.py). Aqui solo el aspecto visual.
  const dropZone = $("drop-zone");
  document.addEventListener("dragover", () => dropZone.classList.add("dragging"));
  document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) dropZone.classList.remove("dragging"); });
  document.addEventListener("drop", () => dropZone.classList.remove("dragging"));
  window.bibExpres = {
    onPdfDropped(path) {
      dropZone.classList.remove("dragging");
      if (currentScreen !== "screen-input") showScreen("screen-input");
      inputRaw.value = path;
      doResolve(path);
    },
  };

  // ===== 1b. Confirmar candidato ===================================================

  function showConfirmScreen(query, candidates) {
    $("confirm-sub").textContent = t("confirmSub", { q: query });
    const list = $("confirm-list");
    list.innerHTML = "";
    if (!candidates.length) list.appendChild(el("p", "empty", t("noneFound")));
    candidates.forEach((paper, index) => {
      const card = el("button", "card candidate-card");
      card.appendChild(el("div", "title", paper.title));
      card.appendChild(el("div", "meta", paperMeta(paper)));
      card.addEventListener("click", async () => {
        try {
          const res = await api().confirm_candidate(index);
          if (res.status === "resolved") showParamsScreen(res.paper);
          else { showScreen("screen-input"); setError("input-error", errorText(res)); }
        } catch (err) {
          showScreen("screen-input");
          setError("input-error", unexpected(err));
        }
      });
      list.appendChild(card);
    });
    showScreen("screen-confirm");
  }

  $("confirm-back-btn").addEventListener("click", () => showScreen("screen-input"));

  // ===== 2. Parametros ================================================================

  let currentRoot = null;

  function renderRootPaper(paper) {
    $("params-paper-title").textContent = paper.title;
    const names = LANGUAGE_NAMES[lang] || {};
    const langName = paper.language ? names[paper.language] || paper.language : null;
    $("params-paper-meta").textContent = paperMeta(paper) + (langName ? ` · ${langName}` : "");
    $("param-language-same").textContent = langName ? t("langSame", { lang: langName }) : t("langSameUnknown");
  }

  function showParamsScreen(paper) {
    currentRoot = paper;
    renderRootPaper(paper);
    setError("params-error", "");
    updateEstimate();
    showScreen("screen-params");
  }

  $("params-change-btn").addEventListener("click", () => showScreen("screen-input"));

  const genSeg = $("param-generations-seg");
  function setGenerations(n) {
    $("param-generations").value = String(n);
    genSeg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.value === String(n)));
    updateGenerationsHint();
    updateEstimate();
  }
  function updateGenerationsHint() {
    const n = Number($("param-generations").value);
    $("generations-hint").textContent = n === 1 ? t("genHint1") : n === 2 ? t("genHint2") : t("genHintN", { n });
  }
  genSeg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => setGenerations(Number(b.dataset.value))));

  // Mismo calculo que expansion.planned_expansions(): 1 + F + F^2... recortado
  // por el presupuesto de exploracion.
  function plannedExpansions() {
    const g = Number($("param-generations").value) || 2;
    const f = Number($("param-max-fanout").value) || 20;
    const budget = Number($("param-explore-budget").value) || 30;
    let total = 0, level = 1;
    for (let i = 0; i < g; i++) { total += level; level *= f; if (total >= budget) break; }
    return Math.min(total, budget);
  }
  function updateEstimate() {
    $("params-estimate").textContent = t("estimate", { n: plannedExpansions() });
  }
  ["param-max-fanout", "param-explore-budget"].forEach((id) => $(id).addEventListener("input", updateEstimate));

  $("param-language-mode").addEventListener("change", (e) => {
    $("param-languages").classList.toggle("hidden", e.target.value !== "custom");
  });

  function collectParams() {
    const modes = Array.from(document.querySelectorAll(".param-mode:checked")).map((x) => x.value);
    const docTypes = Array.from(document.querySelectorAll(".param-doctype:checked")).map((x) => x.value);
    return {
      generations: $("param-generations").value,
      max_articles: $("param-max-articles").value,
      max_fanout: $("param-max-fanout").value,
      explore_budget: $("param-explore-budget").value,
      modes: modes.length ? modes : ["references", "citations"],
      relevance_threshold: $("param-threshold").value,
      weight_topic: $("param-weight-topic").value,
      weight_citations: $("param-weight-citations").value,
      weight_recency: $("param-weight-recency").value,
      weight_coupling: $("param-weight-coupling").value,
      weight_keywords: $("param-weight-keywords").value,
      allowed_doc_types: docTypes,
      require_open_access: $("param-open-access").checked,
      language_mode: $("param-language-mode").value,
      languages: $("param-languages").value,
    };
  }

  $("search-btn").addEventListener("click", async () => {
    setError("params-error", "");
    showProgress(t("searching"));
    startProgressPolling();
    try {
      const res = await api().search(collectParams());
      stopProgressPolling();
      refreshQuota();
      if (res.status === "ok") {
        // "Solo lo que puedo leer" en parametros = la casilla de ocultar en resultados
        $("hide-unreadable").checked = $("param-readable-only").checked;
        showResultsScreen(res);
        notifyIfAway(res.cancelled ? "cancelled" : "ok");
      } else {
        showScreen("screen-params");
        setError("params-error", errorText(res));
        notifyIfAway("error", errorText(res));
      }
    } catch (err) {
      stopProgressPolling();
      showScreen("screen-params");
      setError("params-error", unexpected(err));
      notifyIfAway("error", t("errUnexpected"));
    }
  });

  // ===== 3. Progreso ====================================================================

  const SLOW_AFTER_SECONDS = 30;
  let progressTimer = null;

  function showProgress(message) {
    $("progress-message").textContent = message;
    $("search-progress").classList.add("hidden");
    showScreen("screen-progress");
  }

  function renderProgress(p) {
    if (!p || p.status === "idle") return;
    const pct = p.status === "finished" ? 100 : Math.min(100, Math.round((p.explored / Math.max(p.planned, 1)) * 100));
    $("progress-fill").style.width = `${pct}%`;
    document.querySelector(".progress-track").setAttribute("aria-valuenow", String(pct));
    const stats = $("progress-stats");
    stats.innerHTML = "";
    const part = (label, value, before) => {
      const s = el("span");
      const b = el("b", null, value);
      if (before) { s.appendChild(document.createTextNode(label + " ")); s.appendChild(b); }
      else { s.appendChild(b); s.appendChild(document.createTextNode(" " + label)); }
      stats.appendChild(s);
    };
    part(t("explored"), `${p.explored} / ${p.planned}`, true);
    part(t("candidatesSeen"), fmtNum(p.candidates), false);
    part(t("generation"), String(p.generation || 1), true);
    $("progress-current").textContent = p.current_title || "—";
    const activity = $("progress-activity");
    const idle = Math.round(p.idle_seconds || 0);
    activity.classList.toggle("slow", idle >= SLOW_AFTER_SECONDS);
    activity.textContent = idle >= SLOW_AFTER_SECONDS ? t("slowActivity", { s: idle })
      : idle <= 1 ? t("working") : t("lastActivity", { s: idle });
  }

  function startProgressPolling() {
    $("search-progress").classList.remove("hidden");
    $("progress-fill").style.width = "0%";
    $("progress-stats").textContent = "";
    $("progress-current").textContent = "—";
    $("progress-activity").textContent = t("starting");
    const cancelBtn = $("cancel-search-btn");
    cancelBtn.disabled = false;
    cancelBtn.textContent = t("cancel");
    progressTimer = setInterval(async () => {
      try { renderProgress(await api().get_progress()); refreshQuota(); } catch (err) { console.error(err); }
    }, 500);
  }

  function stopProgressPolling() {
    if (progressTimer !== null) clearInterval(progressTimer);
    progressTimer = null;
  }

  $("cancel-search-btn").addEventListener("click", async () => {
    const btn = $("cancel-search-btn");
    btn.disabled = true;
    btn.textContent = t("cancelling");
    try { await api().cancel_search(); } catch (err) { console.error(err); }
  });

  // ===== 4. Resultados ==================================================================

  const lastResults = { papers: [], candidates: 0, cancelled: false };
  let currentExcludedIndices = [];
  let curationDiscardedCount = 0;
  const openWhy = new Set();

  // Ocultos por "no lo puedo leer". El padre (indice 0) nunca se oculta.
  function hiddenIndices() {
    const hideUnreadable = $("hide-unreadable").checked;
    const hideUnknown = hideUnreadable && $("hide-unknown").checked;
    const hidden = [];
    lastResults.papers.forEach((p, i) => {
      if (i === 0 || !hideUnreadable) return;
      if (p.access_status === "none" || (hideUnknown && (p.access_status === "unknown" || !p.access_status))) hidden.push(i);
    });
    return hidden;
  }

  // Orden y busqueda solo cambian como se ve la lista, no lo que se exporta.
  function visibleOrder() {
    const hidden = new Set(hiddenIndices());
    const query = $("results-search").value.trim().toLowerCase();
    let idx = lastResults.papers.map((_, i) => i).filter((i) => !hidden.has(i));
    if (query) {
      idx = idx.filter((i) => {
        const p = lastResults.papers[i];
        return `${p.title} ${(p.authors || []).join(" ")} ${p.venue || ""}`.toLowerCase().includes(query);
      });
    }
    const sort = $("results-sort").value;
    const rest = idx.filter((i) => i !== 0);
    if (sort === "author") {
      const key = (i) => ((lastResults.papers[i].authors || [])[0] || "~").split(" ").slice(-1)[0].toLowerCase();
      rest.sort((a, b) => key(a).localeCompare(key(b), lang));
    } else if (sort === "year") {
      rest.sort((a, b) => (lastResults.papers[b].year || 0) - (lastResults.papers[a].year || 0));
    }
    return idx.includes(0) ? [0, ...rest] : rest;
  }

  async function openExternal(url) {
    try { await api().open_link(url); } catch (err) { console.error(err); }
  }

  function whyBlock(paper) {
    const bd = paper.score_breakdown;
    const box = el("div", "why");
    box.appendChild(el("b", null, t("whyTitle")));
    const bars = el("div", "bars");
    const addBar = (label, value) => {
      bars.appendChild(el("span", null, label));
      const track = el("span", "track");
      const fill = el("i");
      fill.style.width = `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
      track.appendChild(fill);
      bars.appendChild(track);
      bars.appendChild(el("span", null, value.toFixed(2)));
    };
    addBar(t("whyRelevance"), bd.relevancia);
    addBar(bd.conexiones > 1 ? t("whyConnN", { n: bd.conexiones }) : t("whyConn1"), bd.conexiones_score);
    addBar(t("whyKeywords"), bd.palabras_clave_score);
    box.appendChild(bars);
    if ((bd.palabras_clave || []).length) {
      const kw = el("div", "kw");
      bd.palabras_clave.forEach((k) => kw.appendChild(el("span", null, k)));
      box.appendChild(kw);
    }
    return box;
  }

  function paperCard(paper, index) {
    const card = el("div", "card paper");
    const score = el("div", "score");
    if (index === 0) {
      score.appendChild(el("span", "badge b-root", "★"));
    } else {
      const v = paper.relevance_score || 0;
      score.appendChild(el("div", "v", v.toFixed(2)));
      const mini = el("div", "mini");
      const fill = el("i");
      fill.style.width = `${Math.round(v * 100)}%`;
      mini.appendChild(fill);
      score.appendChild(mini);
    }
    card.appendChild(score);

    const main = el("div");
    main.appendChild(el("div", "t", paper.title));
    main.appendChild(el("div", "m", (index === 0 ? t("rootPaper") + " · " : "") + paperMeta(paper)));
    card.appendChild(main);

    const side = el("div", "side");
    side.appendChild(el("span", `badge b-${paper.access_status || "unknown"}`, accessLabel(paper)));
    if (paper.access_url) {
      const open = el("button", "btn ghost small", paper.access_status === "open" || paper.access_status === "open_bronze" ? t("openFree") : t("openLibrary"));
      open.addEventListener("click", () => openExternal(paper.access_url));
      side.appendChild(open);
    }
    if (index !== 0 && paper.score_breakdown) {
      const whyBtn = el("button", "btn text small", t("whyBtn"));
      whyBtn.setAttribute("aria-expanded", String(openWhy.has(index)));
      whyBtn.addEventListener("click", () => {
        if (openWhy.has(index)) openWhy.delete(index); else openWhy.add(index);
        renderResults();
      });
      side.appendChild(whyBtn);
    }
    card.appendChild(side);
    if (openWhy.has(index) && paper.score_breakdown) card.appendChild(whyBlock(paper));
    return card;
  }

  function renderResults() {
    const total = lastResults.papers.length;
    const hidden = hiddenIndices().length;
    const shown = total - hidden;
    $("results-count").textContent = shown === 1 ? t("oneArticle") : t("nArticles", { n: fmtNum(shown) });
    const sub = [t("resultsSub", { c: fmtNum(lastResults.candidates) })];
    if (hidden) sub.push(hidden === 1 ? t("resultsHiddenOne") : t("resultsHidden", { n: hidden }));
    if (lastResults.cancelled) sub.push(t("resultsCancelled"));
    $("results-sub").textContent = sub.join(" · ");
    $("export-btn").textContent = t("exportN", { n: fmtNum(shown) });

    const list = $("results-list");
    list.innerHTML = "";
    const order = visibleOrder();
    if (!order.length) list.appendChild(el("p", "empty", t("noMatches")));
    order.forEach((i) => list.appendChild(paperCard(lastResults.papers[i], i)));
  }

  function renderPublisherList(publishers, selected) {
    const box = $("publisher-list");
    box.innerHTML = "";
    const chosen = new Set(selected || []);
    if (!publishers.length) { box.appendChild(el("p", "hint", t("noPublishers"))); return; }
    publishers.forEach(([name, count]) => {
      const row = el("div", "pub");
      const label = el("label", "check");
      const input = el("input", "param-publisher");
      input.type = "checkbox";
      input.value = name;
      input.checked = chosen.has(name);
      label.appendChild(input);
      label.appendChild(el("span", null, name));
      row.appendChild(label);
      row.appendChild(el("span", "count", String(count)));
      box.appendChild(row);
    });
  }

  function showResultsScreen(res) {
    lastResults.papers = res.papers;
    lastResults.cancelled = !!res.cancelled;
    lastResults.candidates = res.candidates ?? res.count;
    openWhy.clear();
    renderPublisherList(res.publishers || [], res.selected_publishers || []);
    $("publishers-saved").classList.add("hidden");
    $("results-search").value = "";
    renderResults();
    showScreen("screen-results");
  }

  ["hide-unreadable", "hide-unknown", "results-sort"].forEach((id) => $(id).addEventListener("change", renderResults));
  $("results-search").addEventListener("input", renderResults);

  $("save-publishers-btn").addEventListener("click", async () => {
    const chosen = Array.from(document.querySelectorAll(".param-publisher:checked")).map((x) => x.value);
    try {
      const res = await api().set_publishers(chosen);
      if (res.status === "ok") {
        lastResults.papers = res.papers;
        renderResults();
        $("publishers-saved").classList.remove("hidden");
      }
    } catch (err) { console.error(err); }
  });

  $("new-search-btn").addEventListener("click", () => showScreen(currentRoot ? "screen-params" : "screen-input"));

  $("export-btn").addEventListener("click", () => {
    currentExcludedIndices = hiddenIndices();
    curationDiscardedCount = 0;
    openExportScreen();
  });

  // ===== 5. Curacion ===================================================================

  let curationOrder = []; // indice real en lastResults.papers de cada tarjeta
  let curationIndex = 0;
  let curationDiscarded = new Set();
  let curationHistory = [];

  function showCurationCard() {
    if (curationIndex >= curationOrder.length) { finishCuration(); return; }
    const paper = lastResults.papers[curationOrder[curationIndex]];
    const card = $("curation-card");
    card.style.transform = "";
    const metaRow = $("curation-meta-row");
    metaRow.innerHTML = "";
    metaRow.appendChild(el("span", `badge b-${paper.access_status || "unknown"}`, accessLabel(paper)));
    const bd = paper.score_breakdown;
    if (bd) {
      const linked = bd.conexiones > 1 ? t("linkedN", { n: bd.conexiones }) : t("linked1");
      metaRow.appendChild(el("span", "chip", `${(paper.relevance_score || 0).toFixed(2)} · ${linked}`));
      if ((bd.palabras_clave || []).length) metaRow.appendChild(el("span", "chip", bd.palabras_clave.slice(0, 3).join(" · ")));
    }
    card.querySelector(".title").textContent = paper.title;
    card.querySelector(".meta").textContent = paperMeta(paper);
    card.querySelector(".abstract").textContent = paper.abstract || t("noAbstract");
    const kept = curationIndex - curationDiscarded.size;
    $("curation-counter").textContent = `${t("reviewed", { i: curationIndex, n: curationOrder.length })} · ${t("kept", { k: kept })}`;
    $("curation-progress").style.width = `${Math.round((curationIndex / curationOrder.length) * 100)}%`;
    $("curation-undo-btn").disabled = curationHistory.length === 0;
  }

  function decideCuration(keep) {
    const index = curationOrder[curationIndex];
    curationHistory.push({ index, keep });
    if (!keep) curationDiscarded.add(index);
    curationIndex += 1;
    showCurationCard();
  }

  function undoCuration() {
    const last = curationHistory.pop();
    if (!last) return;
    curationDiscarded.delete(last.index);
    curationIndex -= 1;
    showCurationCard();
  }

  function finishCuration() {
    currentExcludedIndices = Array.from(new Set([...curationDiscarded, ...hiddenIndices()]));
    curationDiscardedCount = curationDiscarded.size;
    openExportScreen();
  }

  $("curate-btn").addEventListener("click", () => {
    const hidden = new Set(hiddenIndices());
    // El padre no se cura: va siempre en el resultado
    curationOrder = lastResults.papers.map((_, i) => i).filter((i) => i !== 0 && !hidden.has(i));
    curationIndex = 0;
    curationDiscarded = new Set();
    curationHistory = [];
    if (!curationOrder.length) { finishCuration(); return; }
    showCurationCard();
    showScreen("screen-curation");
  });

  $("curation-discard-btn").addEventListener("click", () => decideCuration(false));
  $("curation-keep-btn").addEventListener("click", () => decideCuration(true));
  $("curation-finish-btn").addEventListener("click", finishCuration);
  $("curation-undo-btn").addEventListener("click", undoCuration);

  document.addEventListener("keydown", (e) => {
    if (currentScreen !== "screen-curation") return;
    if (e.target instanceof Element && e.target.matches("input, textarea, select")) return;
    if (e.key === "ArrowLeft") decideCuration(false);
    else if (e.key === "ArrowRight") decideCuration(true);
    else if (e.key === "z" || e.key === "Z") undoCuration();
  });

  // Arrastrar la tarjeta: botones y teclado siguen siendo lo principal
  (() => {
    const card = $("curation-card");
    const DRAG_THRESHOLD = 120;
    let startX = null;
    card.addEventListener("pointerdown", (e) => { startX = e.clientX; card.setPointerCapture(e.pointerId); card.style.transition = "none"; });
    card.addEventListener("pointermove", (e) => {
      if (startX === null) return;
      const dx = e.clientX - startX;
      card.style.transform = `translateX(${dx}px) rotate(${dx / 20}deg)`;
    });
    card.addEventListener("pointerup", (e) => {
      if (startX === null) return;
      const dx = e.clientX - startX;
      startX = null;
      card.style.transition = "";
      if (dx > DRAG_THRESHOLD) decideCuration(true);
      else if (dx < -DRAG_THRESHOLD) decideCuration(false);
      else card.style.transform = "";
    });
  })();

  // ===== 6. Exportar ====================================================================

  let exportFormat = "bibtex";

  function selectFormat(format) {
    exportFormat = format;
    document.querySelectorAll(".fmt").forEach((b) => b.classList.toggle("on", b.dataset.format === format));
    // Cambiar de formato invalida la ruta elegida (por seguridad, Python solo
    // escribe en rutas elegidas en el dialogo): se vuelve a elegir.
    $("export-path").value = "";
  }
  document.querySelectorAll(".fmt").forEach((b) => b.addEventListener("click", () => selectFormat(b.dataset.format)));

  function renderExportSummary() {
    const hidden = hiddenIndices().length;
    $("sum-out").textContent = fmtNum(lastResults.papers.length - currentExcludedIndices.length);
    $("sum-discarded").textContent = fmtNum(curationDiscardedCount);
    $("sum-hidden").textContent = fmtNum(hidden);
  }

  function openExportScreen() {
    setError("export-error", "");
    $("export-success").classList.add("hidden");
    $("export-path").value = "";
    selectFormat(exportFormat);
    renderExportSummary();
    showScreen("screen-export");
  }

  $("export-pick-btn").addEventListener("click", async () => {
    try {
      const base = lang === "en" ? "bibliography" : "bibliografia";
      const path = await api().pick_save_path(`${base}.${FORMAT_EXTENSIONS[exportFormat]}`);
      if (path) $("export-path").value = path;
    } catch (err) {
      setError("export-error", unexpected(err));
    }
  });

  $("export-confirm-btn").addEventListener("click", async () => {
    const path = $("export-path").value;
    if (!path) { setError("export-error", t("pickFirst")); return; }
    try {
      const res = await api().export(path, exportFormat, currentExcludedIndices, lang);
      if (res.status === "ok") {
        setError("export-error", "");
        $("export-success-text").textContent = t("exported", { n: fmtNum(res.count), name: res.name || path });
        $("export-success").classList.remove("hidden");
      } else {
        setError("export-error", errorText(res));
      }
    } catch (err) {
      setError("export-error", unexpected(err));
    }
  });

  $("export-new-search-btn").addEventListener("click", goHome);

  $("open-folder-btn").addEventListener("click", async () => {
    try { await api().open_export_folder(); } catch (err) { console.error(err); }
  });

  $("export-back-btn").addEventListener("click", () => showScreen("screen-results"));

  // ===== Ajustes ======================================================================

  function flash(message, isError) {
    const box = $("settings-saved");
    box.textContent = message;
    box.classList.toggle("error-text", !!isError);
    box.classList.remove("hidden");
  }

  $("settings-btn").addEventListener("click", async () => {
    if (currentScreen !== "screen-settings") screenBeforeSettings = currentScreen === "screen-progress" ? "screen-params" : currentScreen;
    try {
      const s = await api().get_settings();
      $("settings-email").value = s.contact_email || "";
      $("settings-key").value = s.semantic_scholar_api_key || "";
      $("settings-library").value = s.library_link_template || "";
      notifyOn = s.ui_notify !== "off";
      $("settings-notify").checked = notifyOn;
    } catch (err) { console.error(err); }
    $("settings-saved").classList.add("hidden");
    applyTheme();
    applyLanguage();
    showScreen("screen-settings");
  });

  $("settings-lang-seg").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => setLanguage(b.dataset.value)));
  $("settings-notify").addEventListener("change", async (e) => {
    notifyOn = e.target.checked;
    try { await api().save_settings({ UI_NOTIFY: notifyOn ? "on" : "off" }); } catch (err) { console.error(err); }
  });

  $("settings-notify-test-btn").addEventListener("click", async () => {
    try {
      const res = await api().test_notification(lang);
      flash(res.shown ? t("notifyTested") : t("notifyFailed"), !res.shown);
    } catch (err) { flash(unexpected(err), true); }
  });

  $("settings-theme-seg").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
    theme = b.dataset.value;
    applyTheme();
    try { await api().save_settings({ UI_THEME: theme }); } catch (err) { console.error(err); }
  }));

  $("settings-save-btn").addEventListener("click", async () => {
    try {
      const res = await api().save_settings({
        CONTACT_EMAIL: $("settings-email").value.trim(),
        SEMANTIC_SCHOLAR_API_KEY: $("settings-key").value.trim(),
        LIBRARY_LINK_TEMPLATE: $("settings-library").value.trim(),
      });
      if (res && res.status === "error") flash(errorText(res), true);
      else flash(t("saved"), false);
    } catch (err) { flash(unexpected(err), true); }
  });

  $("settings-library-test-btn").addEventListener("click", async () => {
    try {
      const res = await api().test_library_link($("settings-library").value.trim());
      if (res.status === "ok") flash(t("libraryTested"), false);
      else flash(errorText(res), true);
    } catch (err) { flash(unexpected(err), true); }
  });

  $("settings-back-btn").addEventListener("click", () => showScreen(screenBeforeSettings));

  // ===== Arranque ========================================================================

  async function start() {
    try {
      const s = await api().get_settings();
      if (s.ui_language === "es" || s.ui_language === "en") lang = s.ui_language;
      if (["system", "light", "dark"].includes(s.ui_theme)) theme = s.ui_theme;
      notifyOn = s.ui_notify !== "off";
    } catch (err) { console.error(err); }
    applyTheme();
    setGenerations(2);
    applyLanguage();
    refreshQuota();
    setInterval(refreshQuota, 60000); // Python descuenta el tiempo hasta el reinicio
    showScreen("screen-input");
  }

  // La API de pywebview llega un poco despues de cargar la pagina
  if (window.pywebview && window.pywebview.api) start();
  else window.addEventListener("pywebviewready", start);
})();
