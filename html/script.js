// script.js (ES module)

function initTooltips() {
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  tooltipTriggerList.forEach((el) => {
    const tooltip = new bootstrap.Tooltip(el, {
      placement: "right",
      trigger: "hover focus",
      delay: { show: 700, hide: 100 },
    });
    el.addEventListener("click", () => {
      tooltip.hide();
      el.blur();
    });
    el.addEventListener("mouseleave", () => tooltip.hide());
  });
}


function buildTimelineTicks(trackEl, ticks, totalMeasures) {
  if (!trackEl) return;
  trackEl.querySelectorAll(".timeline-tick").forEach((node) => node.remove());
  ticks.forEach((tick) => {
    const left = totalMeasures ? (tick.measure / totalMeasures) * 100 : 0;
    const tickEl = document.createElement("div");
    tickEl.className = `timeline-tick ${tick.tempo ? "tick-tempo" : "tick-meter"}`;
    tickEl.style.left = `${Math.max(0, Math.min(100, left))}%`;

    const above = document.createElement("div");
    above.className = "tick-above";
    above.textContent = tick.tempo || tick.meter || "";
    tickEl.appendChild(above);

    if (tick.tempo && tick.meter) {
      const above2 = document.createElement("div");
      above2.className = "tick-above";
      above2.textContent = tick.meter;
      tickEl.appendChild(above2);
    }

    const mark = document.createElement("div");
    mark.className = "tick-mark";
    tickEl.appendChild(mark);

    const below = document.createElement("div");
    below.className = "tick-below";
    below.textContent = tick.key || "";
    tickEl.appendChild(below);

    trackEl.appendChild(tickEl);
  });
}

function initGradeOptions() {
  const select = document.getElementById("targetGradeSelect");
  const fullToggle = document.getElementById("fullGradeSearch");
  if (!select || !fullToggle) return;

  const baseOptions = [
    { value: "0.5", label: ".5" },
    { value: "1", label: "1" },
    { value: "2", label: "2" },
    { value: "3", label: "3" },
    { value: "4", label: "4" },
    { value: "5", label: "5+" },
  ];

  const fullOptions = [
    { value: "0.5", label: ".5" },
    { value: "1", label: "1" },
    { value: "1.5", label: "1.5" },
    { value: "2", label: "2" },
    { value: "2.5", label: "2.5" },
    { value: "3", label: "3" },
    { value: "3.5", label: "3.5" },
    { value: "4", label: "4" },
    { value: "4.5", label: "4.5" },
    { value: "5", label: "5+" },
  ];

  const renderOptions = (options) => {
    const current = select.value;
    select.innerHTML = "";
    options.forEach(({ value, label }) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    });
    if (options.some((opt) => opt.value === current)) {
      select.value = current;
    }
  };

  const sync = () => {
    renderOptions(fullToggle.checked ? fullOptions : baseOptions);
  };

  fullToggle.addEventListener("change", sync);
  sync();
}

async function initVerovio() {
  console.log("initVerovio() starting…");

  // Clean URL + storage (debug)
  const url = new URL(location.href);
  url.searchParams.delete("view");
  if (url.hash && url.hash.includes("view=")) url.hash = "";
  history.replaceState({}, "", url.toString());
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch {}

  // Load Verovio
  await import("https://editor.verovio.org/javascript/app/verovio-app.js");
  console.log(
    "Verovio loaded:",
    typeof window.Verovio,
    typeof window.Verovio?.App,
  );

  const appEl = document.getElementById("app");
  if (!appEl) return console.error("Missing #app element");

  // (Optional) make it obvious where it is
  appEl.style.minHeight = "800px";
  appEl.style.border = "1px solid lightgray";

  let app = new window.Verovio.App(appEl, {
    defaultView: "document",
    documentZoom: 3,
  });

  function ensureZoomWrapper() {
    let root = appEl.querySelector(".verovio-zoom-root");
    if (!root) {
      root = document.createElement("div");
      root.className = "verovio-zoom-root";

      // move current children into wrapper
      while (appEl.firstChild) root.appendChild(appEl.firstChild);
      appEl.appendChild(root);
    }
    return root;
  }

  function setCssZoomPercent(pct) {
    const root = ensureZoomWrapper();
    const scale = Math.max(0.25, Math.min(4, pct / 100));
    root.style.transform = `scale(${scale})`;
  }

  const BASE_ZOOM = 3;
  let currentZoomPct = 100;

  const zoomInput = document.getElementById("zoomPct");
  const zoomApply = document.getElementById("zoomApply");

  if (zoomInput) zoomInput.value = String(currentZoomPct);

  // helper: apply zoom with best available method
function ensureZoomWrapper() {
  let root = appEl.querySelector(".verovio-zoom-root");
  if (!root) {
    root = document.createElement("div");
    root.className = "verovio-zoom-root";
    while (appEl.firstChild) root.appendChild(appEl.firstChild);
    appEl.appendChild(root);
  }
  return root;
}

function setCssZoomPercent(pct) {
  pct = Number(pct);
  if (!Number.isFinite(pct)) return;

  pct = Math.max(25, Math.min(400, pct));
  const scale = pct / 100;

  const root = ensureZoomWrapper();

  // Keep viewport size fixed; only scale the contents
  root.style.transform = `scale(${scale})`;

  // IMPORTANT: prevent the scaled-down content from collapsing layout width/height
  // Give the wrapper an explicit "unscaled" size based on its scroll size.
  // This makes zoom-out not shrink the viewer.
  const unscaledWidth = root.scrollWidth / scale;
  const unscaledHeight = root.scrollHeight / scale;

  root.style.width = `${unscaledWidth}px`;
  root.style.height = `${unscaledHeight}px`;
}

  // click apply
  zoomApply?.addEventListener("click", () => applyZoomPct(zoomInput?.value));

  // allow Enter in the input
  zoomInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyZoomPct(zoomInput.value);
  });

  // File loading
  // File loading (user scores)
  const fileInput = document.getElementById("fileInput");
  const titleEl = document.getElementById("scoreTitle");

  fileInput?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

      if (titleEl)
        titleEl.textContent = `Score Title: ${file.name.replace(/\.[^/.]+$/, "")}`;

      hasActiveScore = true;
      syncScoreActions();

      try {
        const text = await file.text();
      window.__lastScoreText = text;

      // Optional: sniff the file so you know you're not feeding something random
      const head = text.slice(0, 300).toLowerCase();
      const looksLikeMei = head.includes("<mei");
      const looksLikeMusicXml =
        head.includes("<score-partwise") || head.includes("<score-timewise");

      if (!looksLikeMei && !looksLikeMusicXml) {
        console.warn(
          "File doesn't look like MEI or MusicXML. First 300 chars:",
          text.slice(0, 300),
        );
      }

      const p = app.loadData(text);
      if (p?.then) await p;

      console.log(
        "Loaded file:",
        file.name,
        "SVGs:",
        document.querySelectorAll("#app svg").length,
      );
    } catch (err) {
      console.error("Failed to load score:", err);
    }

    const p = app.loadData(text);
    if (p?.then) await p;

    setCssZoomPercent(Number(zoomInput?.value || 100));
  });
  // Target-only toggle (keep your logic)
  const targetOnlyToggle = document.getElementById("targetOnly");
  const observedPane = document.getElementById("observedGradePane");
  if (targetOnlyToggle && observedPane) {
    const sync = () =>
      (observedPane.style.display = targetOnlyToggle.checked ? "none" : "grid");
    targetOnlyToggle.addEventListener("change", sync);
    sync();
  }

  const clearBtn = document.getElementById("clearBtn");
  const loadLabel = document.querySelector(".score-load");
  const clearButton = document.querySelector(".score-clear");
  const scoreActions = document.querySelectorAll(".score-action");
  let hasActiveScore = false;

  const syncScoreActions = () => {
    if (loadLabel) {
      loadLabel.classList.toggle("is-hidden", hasActiveScore);
      loadLabel.setAttribute("aria-disabled", hasActiveScore ? "true" : "false");
    }
    if (clearButton) {
      clearButton.classList.toggle("is-hidden", !hasActiveScore);
      clearButton.disabled = !hasActiveScore;
    }
    scoreActions.forEach((el) => {
      if (el !== clearButton && el !== loadLabel) return;
      el.style.pointerEvents = el.classList.contains("is-hidden") ? "none" : "";
    });
  };

  clearBtn?.addEventListener("click", () => {
    // reset file input so the same file can be selected again
    if (fileInput) fileInput.value = "";

    // reset title
    if (titleEl) titleEl.textContent = "Score Title: --";

    // IMPORTANT: rebuild the app instead of wiping its DOM
    appEl.innerHTML = ""; // ok ONLY because we immediately recreate app
    app = new window.Verovio.App(appEl, {
      defaultView: "document",
      documentZoom: 3,
    });

    hasActiveScore = false;
    syncScoreActions();
    console.log("Verovio app reset.");
  });

  zoomApply?.addEventListener("click", () =>
    setCssZoomPercent(Number(zoomInput.value || 100)),
  );
  zoomInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") setCssZoomPercent(Number(zoomInput.value || 100));
  });

  syncScoreActions();
}

// Run immediately (DOM is already present because your script tag is at the bottom)
initTooltips();
initGradeOptions();
initVerovio().catch((err) => console.error("initVerovio failed:", err));
