// script.js (ES module)
const TS_FONT_PATH = "fonts_ts";
const KS_FONT_PATH = "fonts_key";

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

  let canvas = trackEl.querySelector(".timeline-canvas");
  if (!canvas) {
    canvas = document.createElement("div");
    canvas.className = "timeline-canvas";
    const line = trackEl.querySelector(".timeline-line");
    if (line) {
      line.remove();
      canvas.appendChild(line);
    }
    trackEl.appendChild(canvas);
  }

  // Remove existing ticks
  canvas.querySelectorAll(".timeline-tick").forEach((node) => node.remove());

  // Expect ticks like: [{ measure: 12 }, { measure: 48 }, ...]
  // If you're currently passing objects with tempo/meter/key/etc, that's fine —
  // we ignore all of it now and only use measure.
  const tickList = Array.isArray(ticks) ? [...ticks] : [];
  const startMeasure = 1;
  const endMeasure = Number.isFinite(totalMeasures) ? totalMeasures : null;

  const maxMeasures = endMeasure || 0;
  const viewWidth = trackEl.clientWidth || 0;
  if (maxMeasures > 50 && viewWidth > 0) {
    const measureWidth = viewWidth / 50;
    const canvasWidth = Math.max(viewWidth, maxMeasures * measureWidth);
    canvas.style.width = `${canvasWidth}px`;
    trackEl.style.overflowX = "auto";
  } else {
    canvas.style.width = "100%";
    trackEl.style.overflowX = "hidden";
  }

  if (!tickList.some((tick) => tick?.measure === startMeasure)) {
    tickList.unshift({ measure: startMeasure });
  }
  if (endMeasure && !tickList.some((tick) => tick?.measure === endMeasure)) {
    tickList.push({ measure: endMeasure });
  }

  tickList.forEach((tick) => {
    const measure = Number(tick?.measure);
    if (!Number.isFinite(measure) || measure <= 0) return;

    let left = 0;
    if (endMeasure && endMeasure > 1) {
      left = ((measure - 1) / (endMeasure - 1)) * 100;
    }

    const tickEl = document.createElement("div");
    const isStart = measure === startMeasure;
    const isEnd = measure === endMeasure;
    tickEl.className = `timeline-tick${isStart ? " timeline-tick-start" : ""}${isEnd ? " timeline-tick-end" : ""}`;
    tickEl.style.left = `${Math.max(0, Math.min(100, left))}%`;

    const hasMeter = Boolean(tick.meter);
    const hasTempo = tick.tempo_bpm != null || tick.tempo;
    if (hasMeter || hasTempo) {
      const topRow = document.createElement("div");
      topRow.className = "tick-top";

      if (hasMeter) {
        const [num, den] = String(tick.meter)
          .split("/")
          .map((s) => s.trim());
        if (num && den) {
          topRow.appendChild(makeTimeSigSvgEl(num, den));
        }
      }

      if (hasTempo) {
        const wrap = document.createElement("div");
        wrap.className = "tick-tempo";

        const beatUnit = tick.tempo_beat_unit;
        const bpm = tick.tempo_bpm ?? tick.tempo;
        const svgSrc = tempoSvgForBeatUnit(beatUnit);

        if (svgSrc) {
          const img = document.createElement("img");
          img.className = "tick-tempo-icon";
          img.src = svgSrc;
          img.alt = beatUnit ? `${beatUnit} note` : "Tempo";
          wrap.appendChild(img);
        }

        const txt = document.createElement("span");
        txt.className = "tick-tempo-text";
        if (svgSrc) {
          txt.textContent = `=${bpm}`;
        } else if (beatUnit) {
          txt.textContent = `${beatUnit}=${bpm}`;
        } else {
          txt.textContent = String(bpm);
        }
        wrap.appendChild(txt);

        topRow.appendChild(wrap);
      }

      tickEl.appendChild(topRow);
    }

    const mark = document.createElement("div");
    mark.className = "tick-mark";
    tickEl.appendChild(mark);

    const measureEl = document.createElement("div");
    measureEl.className = "tick-measure";
    measureEl.dataset.measure = String(measure);
    measureEl.textContent = String(measure);
    tickEl.appendChild(measureEl);

    if (tick.key) {
      tickEl.appendChild(makeKeySigSvgEl(tick.key, tick.key_quality));
    }

    canvas.appendChild(tickEl);
  });
}

function digitImg(digit) {
  const img = document.createElement("img");
  img.className = "ts-digit";
  img.src = `${TS_FONT_PATH}/${digit}.svg`;
  img.alt = digit;
  img.draggable = false;

  return img;
}

function renderNumberAsSvgs(n) {
  const row = document.createElement("div");
  row.className = "ts-row";

  const str = String(n).replace(/\D/g, ""); // keep digits only
  for (const ch of str) row.appendChild(digitImg(ch));

  return row;
}

function makeTimeSigSvgEl(numerator, denominator) {
  const wrap = document.createElement("div");
  wrap.className = "tick-timesig";
  wrap.setAttribute(
    "aria-label",
    `Time signature ${numerator} over ${denominator}`,
  );

  wrap.appendChild(renderNumberAsSvgs(numerator));
  wrap.appendChild(renderNumberAsSvgs(denominator));
  return wrap;
}

function tempoSvgForBeatUnit(beatUnit) {
  if (!beatUnit) return null;
  const norm = String(beatUnit).trim().toLowerCase();
  if (norm.includes("dotted")) return null;
  if (norm === "quarter" || norm === "quarter note") {
    return `${TS_FONT_PATH}/quarter.svg`;
  }
  if (norm === "half" || norm === "half note") {
    return `${TS_FONT_PATH}/half.svg`;
  }
  return null;
}

function makeKeySigSvgEl(keyName, quality) {
  const wrap = document.createElement("div");
  wrap.className = "tick-key-wrap";

  const textVal = String(keyName || "").trim();
  const match = textVal.match(/^([A-Ga-g])([#b-])?/);
  if (match) {
    const letter = match[1].toUpperCase();
    const accidental = match[2];
    const letterEl = document.createElement("span");
    letterEl.className = "tick-key-letter";
    letterEl.textContent = letter;
    wrap.appendChild(letterEl);
    if (accidental === "#") {
      const acc = document.createElement("span");
      acc.className = "tick-key-accidental";
      acc.textContent = "♯";
      wrap.appendChild(acc);
    } else if (accidental === "b" || accidental === "-") {
      const acc = document.createElement("span");
      acc.className = "tick-key-accidental";
      acc.textContent = "♭";
      wrap.appendChild(acc);
    }
  }

  if (quality) {
    const q = String(quality).toLowerCase();
    if (q.startsWith("min")) {
      const minorEl = document.createElement("span");
      minorEl.className = "tick-key-minor";
      minorEl.textContent = "m";
      wrap.appendChild(minorEl);
    }
  }

  return wrap;
}

function keySigImg(filename, alt) {
  const img = document.createElement("img");
  img.className = "tick-key-icon";
  img.src = `${KS_FONT_PATH}/${filename}`;
  img.alt = alt;
  img.draggable = false;
  img.onerror = () => console.warn("Missing key SVG:", img.src);
  return img;
}

function toMeasureArray(data) {
  if (!data) return [];

  if (Array.isArray(data))
    return data.map((x) => x.measure).filter(Number.isFinite);

  if (typeof data === "object" && data !== null && "measure" in data) {
    return Number.isFinite(data.measure) ? [data.measure] : [];
  }

  return Object.values(data)
    .map((x) => x?.measure)
    .filter(Number.isFinite);
}


function prepareTimelineTicks() {
  const analysisData = window.analysisResult?.result;
  const notes = analysisData?.analysis_notes || {};
  const keyData = Array.isArray(notes.key)
    ? notes.key
    : Object.values(notes.key || {});
  const tempoData = Array.isArray(notes.tempo)
    ? notes.tempo
    : Object.values(notes.tempo || {});
  const meterData = Array.isArray(notes.meter?.meter_data)
    ? notes.meter.meter_data
    : [];

  const merged = new Map();
  const upsert = (measure, fields) => {
    if (!Number.isFinite(measure)) return;
    const current = merged.get(measure) || { measure };
    merged.set(measure, { ...current, ...fields });
  };

  keyData.forEach((item) => {
    const rawMeasure = Number(item?.measure);
    const measure = rawMeasure <= 0 ? 1 : rawMeasure;
    upsert(measure, {
      key: item?.key || item?.tonic || item?.name,
      key_quality: item?.quality,
    });
  });

  tempoData.forEach((item) => {
    const bpm = item?.bpm ?? item?.tempo ?? item?.number;
    const beatUnit = item?.beat_unit;
    const rawMeasure = Number(item?.measure);
    const measure = rawMeasure <= 0 ? 1 : rawMeasure;
    upsert(measure, {
      tempo_bpm: bpm,
      tempo_beat_unit: beatUnit,
      tempo: bpm != null ? String(bpm) : null,
    });
  });

  meterData.forEach((item) => {
    const rawMeasure = Number(item?.measure);
    const measure = rawMeasure <= 0 ? 1 : rawMeasure;
    upsert(measure, {
      meter: item?.time_signature,
    });
  });

  return [...merged.values()].sort((a, b) => a.measure - b.measure);
}

function formatTimelineTime(seconds) {
  if (!Number.isFinite(seconds)) return "--";
  if (seconds < 60) {
    return `${Math.ceil(seconds)}"`;
  }
  let minutes = Math.floor(seconds / 60);
  let secs = Math.ceil(seconds % 60);
  if (secs >= 60) {
    minutes += 1;
    secs = 0;
  }
  return `${minutes}'${String(secs).padStart(2, "0")}"`;
}

function getSecondsForMeasure(measure, tempoData, totalMeasures) {
  if (!Array.isArray(tempoData) || tempoData.length === 0) {
    return null;
  }
  const segments = [...tempoData].sort(
    (a, b) => Number(a?.measure) - Number(b?.measure),
  );
  const total = Number.isFinite(totalMeasures) ? totalMeasures : null;
  let elapsed = 0;

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const start = Math.max(1, Number(seg?.measure) || 1);
    const next = segments[i + 1];
    const end = Number(next?.measure) || (total != null ? total + 1 : start);
    const length = Math.max(0, end - start);
    const quarterBpm = Number(seg?.quarter_bpm ?? seg?.bpm ?? 100);
    const secPerMeasure = (60 / quarterBpm) * 4;

    if (measure >= start && measure < end) {
      return elapsed + (measure - start) * secPerMeasure;
    }
    elapsed += length * secPerMeasure;
  }

  return null;
}

function setTimelineLabels(totalMeasures, durationString, tempoData) {
  const startEl = document.querySelector("#startingMeasureLabel");
  const endEl = document.querySelector("#endingMeasureLabel");
  const durationCheck = document.querySelector("#toggleDuration");
  let endText = totalMeasures ? String(totalMeasures) : "--";
  const durationText = durationString != null ? String(durationString) : "";
  if (durationCheck?.checked && durationText) {
    const parts = durationText.split("'");
    if (parts.length > 1) {
      const min = parts[0];
      const sec = parts.slice(1).join("'");
      endText = min === "0" ? sec : durationText;
    } else {
      endText = durationText;
    }
  }
  if (startEl) startEl.textContent = durationCheck?.checked ? "0\"" : "1";
  if (endEl) endEl.textContent = endText;
  if (totalMeasures != null || durationString != null) {
    window._timelineMeta = { totalMeasures, durationString, tempoData };
  }

  document.querySelectorAll(".tick-measure").forEach((el) => {
    const measure = Number(el.dataset.measure);
    if (!Number.isFinite(measure)) return;
    if (durationCheck?.checked) {
      const seconds = getSecondsForMeasure(measure, tempoData, totalMeasures);
      el.textContent = formatTimelineTime(seconds);
    } else {
      el.textContent = String(measure);
    }
  });
}

window.prepareTimelineTicks = prepareTimelineTicks;

function getMarkerByLabel(label) {
  const rows = [...document.querySelectorAll(".bar-row")];
  const row = rows.find(
    (r) => r.querySelector(".bar-head span")?.textContent.trim() === label,
  );
  return row ? row.querySelector(".bar .marker") : null;
}

function setMarkerPositions(confidences, opts = {}) {
  if (!confidences) return;
  const emptyLabel = opts.emptyLabel ?? "--";
  const labelMap = {
    availability: "Inst. Availability",
    dynamics: "Dynamics",
    key: "Key",
    range: "Range",
    tempo: "Tempo",
    duration: "Duration",
    articulation: "Articulation",
    rhythm: "Rhythm",
    meter: "Meter",
  };
  Object.entries(confidences).forEach(([key, value]) => {
    const label = labelMap[key];
    if (!label) return;
    const marker = getMarkerByLabel(label);
    if (!marker) return;
    const clamped = value == null ? 0 : Math.max(0, Math.min(0.99, value));
    marker.style.left = `${clamped * 100}%`;
    const scoreEl = document.querySelector(`[data-bar-score="${key}"]`);
    if (scoreEl) {
      if (value == null) {
        scoreEl.textContent = emptyLabel;
      } else {
        const pct = Math.round(value * 100);
        scoreEl.textContent = `${pct}%`;
      }
    }
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

function initAnalysisRequest() {
  const API_BASE = "http://127.0.0.1:5000";
  window.analysisResult = null;
  const analyzeBtn = document.getElementById("analyzeBtn");
  const targetOnly = document.getElementById("targetOnly");
  const stringsOnly = document.getElementById("stringsOnly");
  const fullGrade = document.getElementById("fullGradeSearch");
  const targetGrade = document.getElementById("targetGradeSelect");
  const modalEl = document.getElementById("progressModal");
  const progressBars = document.getElementById("progressBars");
  const progressText = document.getElementById("progressText");
  const progressOkBtn = document.getElementById("progressOkBtn");
  const progressTimer = document.getElementById("progressTimer");
  const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

  if (!analyzeBtn) return;

  if (progressOkBtn) {
    progressOkBtn.addEventListener("click", () => {
      // Just close modal; do NOT clear/rebuild timeline here.

      if (!window.analysisResult) return;

      const totalMeasures = window.analysisResult?.result?.total_measures ?? 0;
      const durationString = window.analysisResult?.result?.duration ?? 0;
      const tempoData = window.analysisResult?.result?.analysis_notes?.tempo ?? [];
      setMarkerPositions(window.analysisResult?.result?.confidences);
      setTimelineLabels(totalMeasures, durationString, tempoData);
    });
  }
  const labelMap = {
    range: "Range",
    key: "Key",
    articulation: "Articulation",
    rhythm: "Rhythm",
    dynamics: "Dynamics",
    availability: "Availability",
    tempo: "Tempo",
    duration: "Duration",
    meter: "Meter",
  };

  const colorMap = {
    range: "orange",
    key: "pink",
    articulation: "green",
    rhythm: "blue",
    dynamics: "red",
    availability: "brown",
    tempo: "yellow",
    duration: "light-green",
    meter: "indigo",
  };

  const barIds = Object.keys(labelMap).reduce((acc, key) => {
    acc[key] = {
      bar: `progress-${key}`,
      pct: `progress-${key}-pct`,
      label: `progress-${key}-label`,
    };
    return acc;
  }, {});

  const ensureProgressBars = () => {
    if (!progressBars) return;
    progressBars.innerHTML = "";
    Object.entries(labelMap).forEach(([key, label]) => {
      const wrapper = document.createElement("div");
      wrapper.className = "progress-item";
      const title = document.createElement("div");
      title.className = "label";
      title.textContent = label;
      const row = document.createElement("div");
      row.className = "progress-row";
      const head = document.createElement("div");
      head.className = "progress-head";
      const headLabel = document.createElement("div");
      headLabel.className = "label";
      headLabel.id = barIds[key].label;
      headLabel.textContent = label;
      const pct = document.createElement("div");
      pct.className = "progress-percent";
      pct.id = barIds[key].pct;
      pct.textContent = "0%";
      head.appendChild(headLabel);
      head.appendChild(pct);
      const barWrap = document.createElement("div");
      barWrap.className = "progress";
      const bar = document.createElement("div");
      bar.className = `progress-bar ${colorMap[key] || ""}`;
      bar.id = barIds[key].bar;
      bar.style.width = "0%";
      barWrap.appendChild(bar);
      row.appendChild(barWrap);
      wrapper.appendChild(head);
      wrapper.appendChild(row);
      progressBars.appendChild(wrapper);
    });
  };

  analyzeBtn.addEventListener("click", async () => {
    const fileInput = document.getElementById("fileInput");
    const file = fileInput?.files?.[0];
    if (!file) {
      alert("Please choose a score file.");
      return;
    }

    const form = new FormData();
    form.append("score_file", file);
    form.append("target_only", String(Boolean(targetOnly?.checked)));
    form.append("strings_only", String(Boolean(stringsOnly?.checked)));
    form.append("full_grade_analysis", String(Boolean(fullGrade?.checked)));
    form.append("target_grade", String(Number(targetGrade?.value || 2)));
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.error || "Failed to start analysis.");
      return;
    }

    const { job_id: jobId } = await res.json();
    if (!jobId) {
      alert("No job id returned.");
      return;
    }

    window.lastJobId = jobId;
    window.analysisResult = null;

    ensureProgressBars();
    if (progressText) progressText.textContent = "Starting analysis...";
    if (progressOkBtn) progressOkBtn.disabled = true;
    if (progressTimer) progressTimer.textContent = "00m00s";
    modal?.show();
    const startedAt = performance.now();
    let timerId = null;
    if (progressTimer) {
      timerId = setInterval(() => {
        const elapsed = (performance.now() - startedAt) / 1000;
        const minutes = Math.floor(elapsed / 60);
        const seconds = Math.floor(elapsed % 60);
        progressTimer.textContent = `${String(minutes).padStart(2, "0")}m${String(seconds).padStart(2, "0")}s`;
      }, 200);
    }

    const es = new EventSource(`${API_BASE}/api/progress/${jobId}`);
    es.onmessage = (evt) => {
      const data = JSON.parse(evt.data);
      if (data.type === "observed") {
        const pct = data.total ? Math.round((data.idx / data.total) * 100) : 0;
        const analyzerKey =
          data.analyzer === "key_range" && data.label
            ? data.label
            : data.analyzer === "tempo_duration" && data.label
              ? data.label
              : data.analyzer;
        const ids = barIds[analyzerKey];
        const bar = ids ? document.getElementById(ids.bar) : null;
        const pctEl = ids ? document.getElementById(ids.pct) : null;
        const labelEl = ids ? document.getElementById(ids.label) : null;
        if (bar) bar.style.width = `${pct}%`;
        if (pctEl) pctEl.textContent = `${pct}%`;
        if (labelEl) {
          const name = labelMap[analyzerKey] || analyzerKey;
          labelEl.textContent = name;
        }
        if (progressText) {
          const name = labelMap[analyzerKey] || analyzerKey;
          progressText.textContent = `${name} grade ${data.grade} - ${pct}%`;
        }
      } else if (data.type === "analyzer") {
        const analyzerKey =
          data.analyzer === "key_range"
            ? "range"
            : data.analyzer === "tempo_duration"
              ? "tempo"
              : data.analyzer;
        const ids = barIds[analyzerKey];
        const bar = ids ? document.getElementById(ids.bar) : null;
        const pctEl = ids ? document.getElementById(ids.pct) : null;
        const labelEl = ids ? document.getElementById(ids.label) : null;
        if (bar && bar.style.width === "0%") {
          bar.style.width = "100%";
        }
        if (pctEl && pctEl.textContent === "0%") {
          pctEl.textContent = "100%";
        }
        if (labelEl) {
          labelEl.textContent = labelMap[analyzerKey] || analyzerKey;
        }
        if (data.analyzer === "tempo_duration") {
          const tempoIds = barIds.tempo;
          const durationIds = barIds.duration;
          const tempoBar = tempoIds
            ? document.getElementById(tempoIds.bar)
            : null;
          const tempoPct = tempoIds
            ? document.getElementById(tempoIds.pct)
            : null;
          const durationBar = durationIds
            ? document.getElementById(durationIds.bar)
            : null;
          const durationPct = durationIds
            ? document.getElementById(durationIds.pct)
            : null;
          if (tempoBar) tempoBar.style.width = "100%";
          if (tempoPct) tempoPct.textContent = "100%";
          if (durationBar) durationBar.style.width = "100%";
          if (durationPct) durationPct.textContent = "100%";
        }
      } else if (data.type === "done") {
        Object.values(barIds).forEach((ids) => {
          const bar = document.getElementById(ids.bar);
          const pctEl = document.getElementById(ids.pct);
          if (bar) bar.style.width = "100%";
          if (pctEl) pctEl.textContent = "100%";
        });
        if (progressText) progressText.textContent = "Done.";
        if (progressOkBtn) progressOkBtn.disabled = false;
        if (timerId) clearInterval(timerId);
        es.close();
        fetch(`${API_BASE}/api/result/${jobId}`)
          .then((r) => r.json())
          .then((result) => {
            window.analysisResult = result;

            const totalMeasures = result?.result?.total_measures ?? 0;
            const durationString = result?.result?.duration ?? 0;
            const tempoData = result?.result?.analysis_notes?.tempo ?? [];

            setTimelineLabels(totalMeasures, durationString, tempoData);

            const ticks = prepareTimelineTicks();
            console.log("ticks:", ticks);
            const track = document.getElementById("timelineTrack");

            buildTimelineTicks(track, ticks, totalMeasures);
          })
          .catch((err) => console.error("Failed to fetch result:", err));
      }
    };

    es.onerror = () => {
      es.close();
      if (progressText) progressText.textContent = "Connection lost.";
      if (timerId) clearInterval(timerId);
      console.warn("Progress stream error; analysisResult not set yet.");
    };
  });
}

function initTimelineToggles() {
  const timeline = document.querySelector(".timeline");
  if (!timeline) return;

  const bind = (id, className) => {
    const el = document.getElementById(id);
    if (!el) return;
    const sync = () => {
      timeline.classList.toggle(className, !el.checked);
    };
    el.addEventListener("change", sync);
    sync();
  };

  bind("toggleMeasures", "hide-measures");
  bind("toggleKey", "hide-key");
  bind("toggleTempo", "hide-tempo");
  bind("toggleMeter", "hide-meter");

  const durationToggle = document.getElementById("toggleDuration");
  if (durationToggle) {
    durationToggle.addEventListener("change", () => {
      const meta = window._timelineMeta || {};
      setTimelineLabels(meta.totalMeasures, meta.durationString, meta.tempoData);
    });
  }
}

function extractScoreTitle(text) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(text, "application/xml");
    const parserError = doc.getElementsByTagName("parsererror")[0];
    if (parserError) return null;

    const pickText = (nodes) => {
      for (const node of nodes) {
        const value = node?.textContent?.trim();
        if (value) return value;
      }
      return null;
    };

    const byTag = (name) => pickText(doc.getElementsByTagName(name));
    const byTagNs = (name) => pickText(doc.getElementsByTagNameNS("*", name));

    return (
      byTag("work-title") ||
      byTagNs("work-title") ||
      byTag("movement-title") ||
      byTagNs("movement-title") ||
      byTag("credit-words") ||
      byTagNs("credit-words") ||
      byTag("title") ||
      byTagNs("title")
    );
  } catch {
    return null;
  }
}

async function initVerovio() {
  console.log("initVerovio() starting...");

  const url = new URL(location.href);
  url.searchParams.delete("view");
  if (url.hash && url.hash.includes("view=")) url.hash = "";
  history.replaceState({}, "", url.toString());
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch {}

  await import("https://editor.verovio.org/javascript/app/verovio-app.js");
  console.log(
    "Verovio loaded:",
    typeof window.Verovio,
    typeof window.Verovio?.App,
  );

  const appEl = document.getElementById("app");
  if (!appEl) return console.error("Missing #app element");

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
    root.style.transform = `scale(${scale})`;

    const unscaledWidth = root.scrollWidth / scale;
    const unscaledHeight = root.scrollHeight / scale;
    root.style.width = `${unscaledWidth}px`;
    root.style.height = `${unscaledHeight}px`;
  }

  const zoomInput = document.getElementById("zoomPct");
  const zoomApply = document.getElementById("zoomApply");
  const fileInput = document.getElementById("fileInput");
  const titleEl = document.getElementById("scoreTitle");
  const clearBtn = document.getElementById("clearBtn");
  const loadLabel = document.querySelector(".score-load");
  const clearButton = document.querySelector(".score-clear");
  const scoreActions = document.querySelectorAll(".score-action");
  const targetOnlyToggle = document.getElementById("targetOnly");
  const observedPane = document.getElementById("observedGradePane");

  let hasActiveScore = false;

  const syncScoreActions = () => {
    if (loadLabel) {
      loadLabel.classList.toggle("is-hidden", hasActiveScore);
      loadLabel.setAttribute(
        "aria-disabled",
        hasActiveScore ? "true" : "false",
      );
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

  fileInput?.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fallbackTitle = file.name.replace(/\.[^/.]+$/, "");
    if (titleEl) {
      titleEl.textContent = `Score Title: ${fallbackTitle}`;
    }

    hasActiveScore = true;
    syncScoreActions();

    try {
      const text = await file.text();
      window.__lastScoreText = text;
      const xmlTitle = extractScoreTitle(text);
      if (titleEl) {
        const cleanTitle =
          xmlTitle && xmlTitle.toLowerCase() !== "title"
            ? xmlTitle
            : fallbackTitle;
        titleEl.textContent = `Score Title: ${cleanTitle}`;
      }

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

    setCssZoomPercent(Number(zoomInput?.value || 100));
  });

  if (targetOnlyToggle && observedPane) {
    const sync = () =>
      (observedPane.style.display = targetOnlyToggle.checked ? "none" : "grid");
    targetOnlyToggle.addEventListener("change", sync);
    sync();
  }

  clearBtn?.addEventListener("click", () => {
    if (fileInput) fileInput.value = "";
    if (titleEl) titleEl.textContent = "Score Title: --";

    appEl.innerHTML = "";
    app = new window.Verovio.App(appEl, {
      defaultView: "document",
      documentZoom: 3,
    });

    hasActiveScore = false;
    syncScoreActions();
    console.log("Verovio app reset.");
    setMarkerPositions(
      {
        availability: null,
        dynamics: null,
        key: null,
        range: null,
        tempo: null,
        duration: null,
        articulation: null,
        rhythm: null,
        meter: null,
      },
      { emptyLabel: "--" },
    );
    const track = document.getElementById("timelineTrack");
    if (track) {
      track.querySelectorAll(".timeline-tick").forEach((node) => node.remove());
    }
    setTimelineLabels();
  });

  zoomApply?.addEventListener("click", () =>
    setCssZoomPercent(Number(zoomInput?.value || 100)),
  );
  zoomInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") setCssZoomPercent(Number(zoomInput.value || 100));
  });

  syncScoreActions();
}

// Run immediately (DOM is already present because your script tag is at the bottom)
initTooltips();
initGradeOptions();
initAnalysisRequest();
initTimelineToggles();
initVerovio().catch((err) => console.error("initVerovio failed:", err));
setTimelineLabels();
