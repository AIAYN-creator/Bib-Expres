(() => {
  "use strict";

  const FORMAT_EXTENSIONS = { bibtex: "bib", ris: "ris", csljson: "json" };

  const screens = {};
  document.querySelectorAll(".screen").forEach((el) => (screens[el.id] = el));

  function showScreen(id) {
    Object.values(screens).forEach((el) => el.classList.add("hidden"));
    screens[id].classList.remove("hidden");
  }

  function showProgress(message) {
    document.getElementById("progress-message").textContent = message;
    showScreen("screen-progress");
  }

  // Red/servidor caidos, o cualquier fallo inesperado en Python: sin esto la
  // pantalla se queda colgada en el spinner sin ninguna pista de que algo fue mal.
  function describeUnexpectedError(err) {
    console.error(err);
    return "Ha ocurrido un error inesperado. Prueba de nuevo -- si se repite, revisa el log de la aplicación.";
  }

  function setError(elId, message) {
    const el = document.getElementById(elId);
    if (message) {
      el.textContent = message;
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  }

  function paperMeta(paper) {
    const authors = (paper.authors || []).slice(0, 3).join(", ") || "autores desconocidos";
    const year = paper.year || "s.f.";
    return `${authors} (${year})${paper.venue ? " -- " + paper.venue : ""}`;
  }

  // -- Pantalla 1: identificar el paper padre --------------------------------

  const inputRaw = document.getElementById("input-raw");

  async function doResolve(raw) {
    if (!raw || !raw.trim()) {
      setError("input-error", "Escribe o pega algo primero.");
      return;
    }
    setError("input-error", "");
    showProgress("Resolviendo el paper padre...");
    try {
      const res = await window.pywebview.api.resolve(raw.trim());
      if (res.status === "resolved") {
        showParamsScreen(res.paper);
      } else if (res.status === "needs_confirmation") {
        showConfirmScreen(res.query, res.candidates);
      } else {
        showScreen("screen-input");
        setError("input-error", res.message || "No se ha podido resolver.");
      }
    } catch (err) {
      showScreen("screen-input");
      setError("input-error", describeUnexpectedError(err));
    }
  }

  document.getElementById("resolve-btn").addEventListener("click", () => doResolve(inputRaw.value));
  inputRaw.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doResolve(inputRaw.value);
  });

  document.getElementById("pick-pdf-btn").addEventListener("click", async () => {
    try {
      const path = await window.pywebview.api.pick_pdf();
      if (path) {
        inputRaw.value = path;
        doResolve(path);
      }
    } catch (err) {
      setError("input-error", describeUnexpectedError(err));
    }
  });

  // -- Pantalla 1b: confirmar candidato ---------------------------------------

  function showConfirmScreen(query, candidates) {
    document.getElementById("confirm-query").textContent = query;
    const list = document.getElementById("confirm-list");
    list.innerHTML = "";
    if (!candidates.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "No se encontró ningún resultado.";
      list.appendChild(p);
    }
    candidates.forEach((paper, index) => {
      const card = document.createElement("button");
      card.className = "candidate-card";
      card.innerHTML = `<div class="title"></div><div class="meta"></div>`;
      card.querySelector(".title").textContent = paper.title;
      card.querySelector(".meta").textContent = paperMeta(paper);
      card.addEventListener("click", async () => {
        try {
          const res = await window.pywebview.api.confirm_candidate(index);
          if (res.status === "resolved") {
            showParamsScreen(res.paper);
          } else {
            showScreen("screen-input");
            setError("input-error", res.message || "Selección inválida.");
          }
        } catch (err) {
          showScreen("screen-input");
          setError("input-error", describeUnexpectedError(err));
        }
      });
      list.appendChild(card);
    });
    showScreen("screen-confirm");
  }

  document.getElementById("confirm-back-btn").addEventListener("click", () => {
    showScreen("screen-input");
  });

  // -- Pantalla 2: parametros de busqueda --------------------------------------

  function showParamsScreen(paper) {
    const chip = document.getElementById("params-paper-chip");
    chip.innerHTML = `<strong></strong><br><span class="hint"></span>`;
    chip.querySelector("strong").textContent = "✓ " + paper.title;
    chip.querySelector(".hint").textContent = paperMeta(paper);
    setError("params-error", "");
    showScreen("screen-params");
  }

  function collectParams() {
    const modes = Array.from(document.querySelectorAll(".param-mode:checked")).map((el) => el.value);
    const allowedDocTypes = Array.from(document.querySelectorAll(".param-doctype:checked")).map(
      (el) => el.value
    );
    return {
      generations: document.getElementById("param-generations").value,
      max_articles: document.getElementById("param-max-articles").value,
      max_fanout: document.getElementById("param-max-fanout").value,
      modes: modes.length ? modes : ["references", "citations"],
      relevance_threshold: document.getElementById("param-threshold").value,
      weight_topic: document.getElementById("param-weight-topic").value,
      weight_citations: document.getElementById("param-weight-citations").value,
      weight_recency: document.getElementById("param-weight-recency").value,
      allowed_doc_types: allowedDocTypes,
      require_open_access: document.getElementById("param-open-access").checked,
    };
  }

  document.getElementById("search-btn").addEventListener("click", async () => {
    setError("params-error", "");
    showProgress("Buscando... puede tardar según los parámetros.");
    try {
      const res = await window.pywebview.api.search(collectParams());
      if (res.status === "ok") {
        showResultsScreen(res);
      } else {
        showScreen("screen-params");
        setError("params-error", res.message || "Error en la búsqueda.");
      }
    } catch (err) {
      showScreen("screen-params");
      setError("params-error", describeUnexpectedError(err));
    }
  });

  // -- Pantalla 4: resultados --------------------------------------------------

  let lastResultsCount = 0;

  function showResultsScreen(res) {
    lastResultsCount = res.count;
    document.getElementById("results-count").textContent = `${res.count} artículos encontrados`;
    const list = document.getElementById("results-list");
    list.innerHTML = "";
    res.papers.forEach((paper) => {
      const row = document.createElement("div");
      row.className = "paper-row";
      row.innerHTML = `<div class="title"></div><div class="meta"></div>`;
      row.querySelector(".title").textContent = paper.title;
      row.querySelector(".meta").textContent = paperMeta(paper);
      list.appendChild(row);
    });
    showScreen("screen-results");
  }

  document.getElementById("new-search-btn").addEventListener("click", () => {
    inputRaw.value = "";
    showScreen("screen-input");
  });

  document.getElementById("export-btn").addEventListener("click", () => {
    setError("export-error", "");
    document.getElementById("export-success").classList.add("hidden");
    document.getElementById("export-path").value = "";
    showScreen("screen-export");
  });

  // -- Pantalla 5: exportar -----------------------------------------------------

  document.getElementById("export-pick-btn").addEventListener("click", async () => {
    try {
      const format = document.getElementById("export-format").value;
      const ext = FORMAT_EXTENSIONS[format];
      const path = await window.pywebview.api.pick_save_path(`bibliografia.${ext}`);
      if (path) document.getElementById("export-path").value = path;
    } catch (err) {
      setError("export-error", describeUnexpectedError(err));
    }
  });

  document.getElementById("export-confirm-btn").addEventListener("click", async () => {
    const path = document.getElementById("export-path").value;
    const format = document.getElementById("export-format").value;
    if (!path) {
      setError("export-error", "Elige antes dónde guardar el fichero.");
      return;
    }
    try {
      const res = await window.pywebview.api.export(path, format);
      if (res.status === "ok") {
        setError("export-error", "");
        const ok = document.getElementById("export-success");
        ok.textContent = `Guardado en ${res.path}`;
        ok.classList.remove("hidden");
      } else {
        setError("export-error", res.message || "No se ha podido exportar.");
      }
    } catch (err) {
      setError("export-error", describeUnexpectedError(err));
    }
  });

  document.getElementById("export-back-btn").addEventListener("click", () => {
    showScreen("screen-results");
  });

  // -- Ajustes --------------------------------------------------------------------

  document.getElementById("settings-btn").addEventListener("click", async () => {
    const settings = await window.pywebview.api.get_settings();
    document.getElementById("settings-email").value = settings.contact_email || "";
    document.getElementById("settings-key").value = settings.semantic_scholar_api_key || "";
    document.getElementById("settings-saved").classList.add("hidden");
    showScreen("screen-settings");
  });

  document.getElementById("settings-save-btn").addEventListener("click", async () => {
    await window.pywebview.api.save_settings({
      CONTACT_EMAIL: document.getElementById("settings-email").value.trim(),
      SEMANTIC_SCHOLAR_API_KEY: document.getElementById("settings-key").value.trim(),
    });
    document.getElementById("settings-saved").classList.remove("hidden");
  });

  document.getElementById("settings-back-btn").addEventListener("click", () => {
    showScreen(lastResultsCount ? "screen-results" : "screen-input");
  });

  showScreen("screen-input");
})();
