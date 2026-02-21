// script.js (ES module)
const TS_FONT_PATH = "fonts_ts";
const KS_FONT_PATH = "fonts_key";

const PART_ANALYZERS = [
  "range",
  "articulation",
  "dynamics",
  "rhythm",
  "availability",
];
const KEY_ANALYSIS_MODES = {
  STRING: "string",
  STANDARD: "standard",
};

function formatGrade(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? "");
  return String(num);
}

function formatConfidencePercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return `${Math.round(num * 100)}%`;
}

function deriveAvailabilityConfidence(availabilityNotes) {
  if (!availabilityNotes || typeof availabilityNotes !== "object") return null;
  const values = Object.values(availabilityNotes)
    .map((item) => item?.availability_confidence)
    .filter((val) => Number.isFinite(val));
  if (values.length === 0) return null;
  const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
  return Math.max(0, Math.min(1, avg));
}

function extractCommentList(comments) {
  if (!comments || typeof comments !== "object") return [];
  return Object.values(comments)
    .map((val) => String(val || "").trim())
    .filter((val) => val);
}

const RANGE_COMMENT_KEYS = new Set([
  "range",
  "crosses_break",
  "harmonic_tolerance",
  "partial_change",
]);

function extractRangeCommentList(comments) {
  if (!comments) return [];
  if (typeof comments === "string") {
    const text = comments.trim();
    return text ? [text] : [];
  }
  if (Array.isArray(comments)) {
    return comments.map((val) => String(val || "").trim()).filter((val) => val);
  }
  if (typeof comments === "object") {
    return Object.entries(comments)
      .filter(([key]) => RANGE_COMMENT_KEYS.has(String(key)))
      .map(([, val]) => String(val || "").trim())
      .filter((val) => val);
  }
  return [];
}

function extractSegmentComments(segment) {
  if (!segment) return [];
  const raw = segment.comments ?? segment.comment ?? null;
  if (typeof raw === "string") {
    const text = raw.trim();
    return text ? [text] : [];
  }
  if (raw && typeof raw === "object") {
    return extractCommentList(raw);
  }
  return [];
}

function getBeatNumber(note) {
  const beatIndex = Number(note?.beat_index);
  if (Number.isFinite(beatIndex)) {
    return beatIndex + 1;
  }
  const offset = Number(note?.offset);
  if (!Number.isFinite(offset)) return null;
  const beat = Math.floor(offset) + 1;
  return beat > 0 ? beat : 1;
}

function normalizeMeasureKey(value) {
  const num = Number(value);
  return Number.isFinite(num) ? String(num) : "—";
}

function normalizeBeatKey(value) {
  const num = Number(value);
  return Number.isFinite(num) ? String(num) : "—";
}

function sortNumericKeys(keys) {
  return [...keys].sort((a, b) => {
    if (a === "—" && b === "—") return 0;
    if (a === "—") return 1;
    if (b === "—") return -1;
    return Number(a) - Number(b);
  });
}

function buildAnalyzerInstrumentIssues(analyzer, instrument, filteredNotes) {
  const issues = {};

  const addIssue = (measure, beat, comment) => {
    const measureKey = normalizeMeasureKey(measure);
    const beatKey = normalizeBeatKey(beat);
    if (!issues[measureKey]) issues[measureKey] = {};
    if (!issues[measureKey][beatKey]) issues[measureKey][beatKey] = [];
    if (comment) {
      const list = issues[measureKey][beatKey];
      if (!list.includes(comment)) list.push(comment);
    }
  };

  if (analyzer === "range") {
    const data = filteredNotes?.range?.[instrument];
    const notes = data?.["Note Data"] || [];
    notes.forEach((note) => {
      const comments = extractRangeCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      comments.forEach((comment) => {
        addIssue(note?.measure, beatNum, comment);
      });
    });
  } else if (analyzer === "articulation") {
    const data = filteredNotes?.articulation?.[instrument];
    const notes = data?.articulation_data || [];
    notes.forEach((note) => {
      const comments = extractCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      comments.forEach((comment) => {
        addIssue(note?.measure, beatNum, comment);
      });
    });
  } else if (analyzer === "rhythm") {
    const data = filteredNotes?.rhythm?.[instrument];
    const notes = data?.note_data || [];
    notes.forEach((note) => {
      const comments = extractCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      comments.forEach((comment) => {
        addIssue(note?.measure, beatNum, comment);
      });
    });
  } else if (analyzer === "dynamics") {
    const data = filteredNotes?.dynamics?.[instrument];
    const issues = Array.isArray(data?.dynamics) ? data.dynamics : [];
    const commentMap = data?.comments || {};
    issues.forEach((item) => {
      if (item?.allowed) return;
      const dynName = item?.dynamic;
      const fallback = dynName
        ? `${dynName} not common for this grade`
        : "Dynamic not common for this grade";
      const comment =
        dynName && commentMap?.[dynName] ? commentMap[dynName] : fallback;
      addIssue(item?.measure, null, comment);
    });
  } else if (analyzer === "availability") {
    const data = filteredNotes?.availability?.[instrument] || {};
    Object.values(data)
      .filter((val) => typeof val === "string")
      .forEach((comment) => addIssue(null, null, comment));
  }

  return issues;
}

function renderGlobalAnalyzerDetails(analyzer, payload) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.remove(
    "detail-body--measure",
    "detail-body--analyzer",
    "detail-body--global",
    "detail-body--list",
  );
  detailsPane.classList.add("detail-body--global");

  if (typeof payload === "string") {
    detailsPane.textContent = payload;
    return;
  }

  const blocks = [];
  const changeComments = new Set();
  const analyzerLabel = analyzer.charAt(0).toUpperCase() + analyzer.slice(1);
  const takeChangeComments = (comments) => {
    const remaining = [];
    comments.forEach((comment) => {
      const text = String(comment || "").trim();
      if (!text) return;
      if (/changes?/i.test(text)) {
        changeComments.add(text);
      } else {
        remaining.push(text);
      }
    });
    return remaining;
  };

  if (analyzer === "key") {
    const segments = Array.isArray(payload?.segments) ? payload.segments : [];
    segments.forEach((seg) => {
      const keyName = seg?.key || seg?.tonic || seg?.name || "Unknown";
      const quality =
        seg?.quality && String(seg.quality).toLowerCase() !== "none"
          ? String(seg.quality)
          : "";
      const title = quality ? `Key: ${keyName} ${quality}` : `Key: ${keyName}`;
      const comments = takeChangeComments(extractSegmentComments(seg));
      blocks.push({
        title,
        measure: seg?.measure,
        comments,
      });
    });
    if (payload?.key_changes && typeof payload.key_changes === "string") {
      const text = payload.key_changes.trim();
      if (text) changeComments.add(text);
    }
  } else if (analyzer === "tempo") {
    const segments = Array.isArray(payload) ? payload : [];
    segments.forEach((seg) => {
      const bpm = seg?.bpm ?? seg?.tempo ?? seg?.number;
      const beatUnit = seg?.beat_unit;
      const beatText = beatUnit ? ` (${beatUnit})` : "";
      const title =
        bpm != null ? `Tempo: ${bpm} BPM${beatText}` : "Tempo issue";
      blocks.push({
        title,
        measure: seg?.measure,
        comments: extractSegmentComments(seg),
      });
    });
  } else if (analyzer === "meter") {
    const segments = Array.isArray(payload) ? payload : [];
    segments.forEach((seg) => {
      const ts = seg?.time_signature || seg?.meter || "Unknown";
      const comments = takeChangeComments(extractSegmentComments(seg));
      blocks.push({
        title: `Meter: ${ts}`,
        measure: seg?.measure,
        comments,
      });
    });
  } else if (analyzer === "duration") {
    if (payload && typeof payload === "object") {
      const length =
        payload.length_string || payload.length || payload.duration;
      const comments = takeChangeComments(extractSegmentComments(payload));
      blocks.push({
        title: length ? `Duration: ${length}` : "Duration issue",
        measure: null,
        comments,
      });
    }
  }

  if (analyzer !== "tempo" && changeComments.size > 0) {
    blocks.unshift({
      title: `${analyzerLabel} changes`,
      measure: null,
      comments: [...changeComments],
    });
  }

  if (blocks.length === 0) {
    detailsPane.textContent = "";
    return;
  }

  blocks.forEach((block) => {
    const wrap = document.createElement("div");
    wrap.className = "detail-block";

    const title = document.createElement("div");
    title.className = "detail-block-title";
    title.textContent = block.title;
    wrap.appendChild(title);

    const line = document.createElement("div");
    line.className = "detail-block-line";
    wrap.appendChild(line);

    if (block.measure != null && Number.isFinite(Number(block.measure))) {
      const measureEl = document.createElement("div");
      measureEl.className = "detail-block-measure";
      measureEl.textContent = `Measure ${block.measure}`;
      wrap.appendChild(measureEl);
    }

    const comments = block.comments || [];
    if (comments.length > 0) {
      const list = document.createElement("ul");
      list.className = "measure-issue-list";
      comments.forEach((comment) => {
        const item = document.createElement("li");
        item.className = "measure-issue-item";
        item.textContent = comment;
        list.appendChild(item);
      });
      wrap.appendChild(list);
    }

    detailsPane.appendChild(wrap);
  });
}

function renderAvailabilityDetails(payload) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.remove(
    "detail-body--measure",
    "detail-body--analyzer",
    "detail-body--global",
  );
  detailsPane.classList.add("detail-body--global");

  if (typeof payload === "string") {
    detailsPane.textContent = payload;
    return;
  }

  if (!payload || typeof payload !== "object") {
    detailsPane.textContent = "";
    return;
  }

  const instruments = Object.keys(payload || {});
  if (instruments.length === 0) {
    detailsPane.textContent = "No issues found.";
    return;
  }

  const targetGrade = Number(
    document.getElementById("targetGradeSelect")?.value ?? NaN,
  );
  const gradeText = Number.isFinite(targetGrade)
    ? ` for grade ${formatGrade(targetGrade)}`
    : "";

  const wrap = document.createElement("div");
  wrap.className = "detail-block";

  const title = document.createElement("div");
  title.className = "detail-block-title";
  title.textContent = `Uncommon instruments detected${gradeText}`;
  wrap.appendChild(title);

  const line = document.createElement("div");
  line.className = "detail-block-line";
  wrap.appendChild(line);

  const list = document.createElement("ul");
  list.className = "measure-issue-list";
  instruments
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .forEach((instrument) => {
      const item = document.createElement("li");
      item.className = "measure-issue-item";
      item.textContent = instrument;
      list.appendChild(item);
    });
  wrap.appendChild(list);

  detailsPane.appendChild(wrap);
}

function renderScoringDetails(payload) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.remove(
    "detail-body--measure",
    "detail-body--analyzer",
    "detail-body--global",
  );
  detailsPane.classList.add("detail-body--global");

  if (typeof payload === "string") {
    detailsPane.textContent = payload;
    return;
  }

  if (!payload || typeof payload !== "object") {
    detailsPane.textContent = "";
    return;
  }

  const summary = payload.summary || {};
  const highlights = Array.isArray(payload.highlights)
    ? payload.highlights
    : [];
  const issues = Array.isArray(payload.issues) ? payload.issues : [];
  const message = payload.message ? String(payload.message) : "";
  const gradeEstimate = payload.grade_estimate;

  const familyLabels = {
    wind: "Woodwinds",
    brass: "Brass",
    string: "Strings",
    percussion: "Percussion",
    keyboard: "Keyboard",
  };
  const groupLabels = {
    high_woodwinds: "High woodwinds",
    mid_woodwinds: "Mid woodwinds",
    low_woodwinds: "Low woodwinds",
    high_brass: "High brass",
    mid_brass: "Mid brass",
    low_brass: "Low brass",
    high_strings: "High strings",
    low_strings: "Low strings",
    percussion: "Percussion",
    keyboard: "Keyboard",
  };

  const appendPercentText = (node, text) => {
    const parts = String(text).split(/(\d+%)/g);
    parts.forEach((part) => {
      if (!part) return;
      if (/^\d+%$/.test(part)) {
        const strong = document.createElement("strong");
        strong.textContent = part;
        node.appendChild(strong);
      } else {
        node.appendChild(document.createTextNode(part));
      }
    });
  };

  const appendBlock = (titleText, items) => {
    const listItems = Array.isArray(items)
      ? items.map((val) => String(val || "").trim()).filter((val) => val)
      : [];
    if (!titleText && listItems.length === 0) return;

    const wrap = document.createElement("div");
    wrap.className = "detail-block";

    if (titleText) {
      const title = document.createElement("div");
      title.className = "detail-block-title";
      title.textContent = titleText;
      wrap.appendChild(title);

      const line = document.createElement("div");
      line.className = "detail-block-line";
      wrap.appendChild(line);
    }

    if (listItems.length > 0) {
      const list = document.createElement("ul");
      list.className = "measure-issue-list";
      const shouldBoldPercent = titleText === "Scoring overview";
      listItems.forEach((itemText) => {
        const item = document.createElement("li");
        item.className = "measure-issue-item";
        if (shouldBoldPercent) {
          appendPercentText(item, itemText);
        } else {
          item.textContent = itemText;
        }
        list.appendChild(item);
      });
      wrap.appendChild(list);
    }

    detailsPane.appendChild(wrap);
  };

  const summaryLines = [];
  if (Number.isFinite(summary.total_parts)) {
    summaryLines.push(`Total parts: ${summary.total_parts}`);
  }

  if (summary.families && typeof summary.families === "object") {
    const familyText = Object.entries(summary.families)
      .map(([name, count]) => {
        const label = familyLabels[name] || String(name).replace(/_/g, " ");
        return `${label} (${count})`;
      })
      .join(", ");
    if (familyText) summaryLines.push(`Families: ${familyText}`);
  }

  if (summary.groups && typeof summary.groups === "object") {
    const groupText = Object.entries(summary.groups)
      .map(([name, count]) => {
        const label = groupLabels[name] || String(name).replace(/_/g, " ");
        return `${label} (${count})`;
      })
      .join(", ");
    if (groupText) summaryLines.push(`Subgroups: ${groupText}`);
  }

  if (Number.isFinite(summary.texture_density)) {
    const pct = Math.round(summary.texture_density * 100);
    const label = summary.texture_label || "Texture density";
    summaryLines.push(`${label}: ${pct}% of parts active on average`);
  }

  if (Number.isFinite(summary.rhythmic_congruency)) {
    const pct = Math.round(summary.rhythmic_congruency * 100);
    summaryLines.push(`Rhythmic congruency: ${pct}%`);
  }

  if (Number.isFinite(summary.harmonic_congruency)) {
    const pct = Math.round(summary.harmonic_congruency * 100);
    summaryLines.push(`Harmonic congruency: ${pct}%`);
  }

  if (Number.isFinite(summary.overall_congruency)) {
    const pct = Math.round(summary.overall_congruency * 100);
    summaryLines.push(`Overall congruency: ${pct}% (harmonic weighted)`);
  }

  if (Number.isFinite(summary.within_group_congruency)) {
    const pct = Math.round(summary.within_group_congruency * 100);
    summaryLines.push(`Within-group congruency: ${pct}%`);
  }

  if (Number.isFinite(summary.cross_group_congruency)) {
    const pct = Math.round(summary.cross_group_congruency * 100);
    summaryLines.push(`Cross-group congruency: ${pct}%`);
  }

  if (Number.isFinite(summary.percussion_rhythm_congruency)) {
    const pct = Math.round(summary.percussion_rhythm_congruency * 100);
    summaryLines.push(`Percussion rhythmic congruency: ${pct}%`);
  }

  void gradeEstimate;

  const overviewItems = [];
  const seen = new Set();
  [...summaryLines, ...highlights].forEach((item) => {
    const text = String(item || "").trim();
    if (!text) return;
    const key = text.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    overviewItems.push(text);
  });

  if (overviewItems.length > 0) {
    appendBlock("Scoring overview", overviewItems);
  } else if (message) {
    detailsPane.textContent = message;
    return;
  }

  const issueItems = issues.length > 0 ? issues : message ? [message] : [];
  if (issueItems.length > 0) {
    appendBlock("Issues", issueItems);
  }
}

function renderAnalyzerInstrumentList(analyzer, payload) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.remove(
    "detail-body--measure",
    "detail-body--analyzer",
    "detail-body--global",
    "detail-body--list",
  );
  detailsPane.classList.add("detail-body--list");
  window._detailLastView = { type: "analyzer_list", analyzer };

  const instrumentList = Object.keys(payload || {});
  if (instrumentList.length === 0) {
    detailsPane.textContent = "";
    return;
  }

  const partOrder = window.analysisResult?.result?.part_order;
  const partFamilies = window.analysisResult?.result?.part_families || {};
  const partGroups = window.analysisResult?.result?.part_groups || {};
  if (Array.isArray(partOrder) && partOrder.length > 0) {
    const orderMap = new Map();
    partOrder.forEach((name, idx) => {
      if (!orderMap.has(name)) orderMap.set(name, idx);
    });
    const ordered = instrumentList.map((name, index) => ({
      name,
      index,
      order: orderMap.has(name) ? orderMap.get(name) : Number.POSITIVE_INFINITY,
    }));
    ordered.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.index - b.index;
    });
    instrumentList.length = 0;
    ordered.forEach((item) => instrumentList.push(item.name));
  }

  instrumentList.forEach((ins) => {
    const btn = document.createElement("button");
    btn.className = "detail-list-btn";
    const group = partGroups?.[ins];
    if (group) {
      btn.classList.add(`detail-list-btn--${String(group).replace(/_/g, "-")}`);
    }
    const family = partFamilies?.[ins];
    if (family) {
      btn.classList.add(`detail-list-btn--${family}`);
    }
    btn.textContent = ins;

    btn.dataset.analyzer = analyzer;
    btn.dataset.instrument = ins;

    btn.addEventListener("click", () => {
      renderAnalyzerInstrumentDetails(analyzer, ins);
    });

    detailsPane.appendChild(btn);
  });
}

function renderAnalyzerInstrumentDetails(analyzer, instrument) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.remove(
    "detail-body--measure",
    "detail-body--global",
    "detail-body--list",
  );
  detailsPane.classList.add("detail-body--analyzer");
  window._detailLastView = { type: "analyzer_detail", analyzer, instrument };

  const header = document.createElement("div");
  header.className = "detail-header";

  const headerRow = document.createElement("div");
  headerRow.className = "detail-header-row";

  const backBtn = document.createElement("button");
  backBtn.type = "button";
  backBtn.className = "detail-back";
  backBtn.textContent = "Back";
  backBtn.addEventListener("click", () => {
    const filtered = window.analysisResult?.result?.analysis_notes_filtered;
    renderAnalyzerInstrumentList(analyzer, filtered?.[analyzer]);
  });

  const title = document.createElement("div");
  const label = analyzer.charAt(0).toUpperCase() + analyzer.slice(1);
  title.className = "detail-title";
  title.textContent = `${label} — ${instrument}`;

  headerRow.appendChild(backBtn);
  headerRow.appendChild(title);
  header.appendChild(headerRow);
  detailsPane.appendChild(header);

  const filtered = window.analysisResult?.result?.analysis_notes_filtered || {};
  const issues = buildAnalyzerInstrumentIssues(analyzer, instrument, filtered);
  const measureKeys = sortNumericKeys(Object.keys(issues));

  if (measureKeys.length === 0) {
    const empty = document.createElement("div");
    empty.className = "measure-empty";
    empty.textContent = "No issues detected for this part.";
    detailsPane.appendChild(empty);
    return;
  }

  measureKeys.forEach((measureKey) => {
    const measureBlock = document.createElement("div");
    measureBlock.className = "detail-measure";

    const measureTitle = document.createElement("div");
    measureTitle.className = "detail-measure-title";
    measureTitle.textContent = `Measure ${measureKey}`;
    measureBlock.appendChild(measureTitle);

    const beats = issues[measureKey] || {};
    const beatKeys = sortNumericKeys(Object.keys(beats));
    beatKeys.forEach((beatKey) => {
      const beatTitle = document.createElement("div");
      beatTitle.className = "detail-beat-title";
      beatTitle.textContent = `Beat ${beatKey}`;
      measureBlock.appendChild(beatTitle);

      const list = document.createElement("ul");
      list.className = "measure-issue-list";
      (beats[beatKey] || []).forEach((comment) => {
        const item = document.createElement("li");
        item.className = "measure-issue-item";
        item.textContent = comment;
        list.appendChild(item);
      });
      measureBlock.appendChild(list);
    });

    detailsPane.appendChild(measureBlock);
  });
}

function handleDetailBack() {
  const last = window._detailLastView;
  const filtered = window.analysisResult?.result?.analysis_notes_filtered;
  if (!last || !filtered) {
    const detailsPane = document.getElementsByClassName("detail-body")[0];
    if (detailsPane) {
      detailsPane.innerHTML = "";
      detailsPane.classList.remove(
        "detail-body--measure",
        "detail-body--analyzer",
        "detail-body--global",
        "detail-body--list",
      );
    }
    return;
  }
  if (last.type === "analyzer_list") {
    renderAnalyzerInstrumentList(last.analyzer, filtered?.[last.analyzer]);
  } else if (last.type === "analyzer_detail") {
    renderAnalyzerInstrumentDetails(last.analyzer, last.instrument);
  } else {
    const detailsPane = document.getElementsByClassName("detail-body")[0];
    if (detailsPane) {
      detailsPane.innerHTML = "";
      detailsPane.classList.remove(
        "detail-body--measure",
        "detail-body--analyzer",
        "detail-body--global",
        "detail-body--list",
      );
    }
  }
}

function addMeasureIssue(index, measure, part, analyzer, comment) {
  if (!Number.isFinite(measure)) return;
  const key = String(measure);
  if (!index[key]) index[key] = {};
  if (!index[key][part]) index[key][part] = {};
  if (!index[key][part][analyzer]) index[key][part][analyzer] = [];
  if (comment) {
    const list = index[key][part][analyzer];
    if (!list.includes(comment)) list.push(comment);
  }
}

function buildMeasureIssueIndex(filteredNotes) {
  const index = {};
  const measures = new Set();

  const noteIssue = (measure, part, analyzer, comments) => {
    if (!comments || comments.length === 0) return;
    comments.forEach((comment) => {
      addMeasureIssue(index, measure, part, analyzer, comment);
      measures.add(Number(measure));
    });
  };

  const rangeData = filteredNotes?.range || {};
  Object.entries(rangeData).forEach(([part, data]) => {
    const notes = data?.["Note Data"] || [];
    notes.forEach((note) => {
      const measure = Number(note?.measure);
      const comments = extractRangeCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      const prefix = Number.isFinite(beatNum) ? `On beat ${beatNum}: ` : "";
      const formatted = comments.map((comment) => `${prefix}${comment}`);
      noteIssue(measure, part, "range", formatted);
    });
  });

  const articulationData = filteredNotes?.articulation || {};
  Object.entries(articulationData).forEach(([part, data]) => {
    const notes = data?.articulation_data || [];
    notes.forEach((note) => {
      const measure = Number(note?.measure);
      const comments = extractCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      const prefix = Number.isFinite(beatNum) ? `On beat ${beatNum}: ` : "";
      const formatted = comments.map((comment) => `${prefix}${comment}`);
      noteIssue(measure, part, "articulation", formatted);
    });
  });

  const rhythmData = filteredNotes?.rhythm || {};
  Object.entries(rhythmData).forEach(([part, data]) => {
    const notes = data?.note_data || [];
    notes.forEach((note) => {
      const measure = Number(note?.measure);
      const comments = extractCommentList(note?.comments);
      const beatNum = getBeatNumber(note);
      const prefix = Number.isFinite(beatNum) ? `On beat ${beatNum}: ` : "";
      const formatted = comments.map((comment) => `${prefix}${comment}`);
      noteIssue(measure, part, "rhythm", formatted);
    });
  });

  const dynamicsData = filteredNotes?.dynamics || {};
  Object.entries(dynamicsData).forEach(([part, data]) => {
    const issues = Array.isArray(data?.dynamics) ? data.dynamics : [];
    const commentMap = data?.comments || {};
    issues.forEach((item) => {
      if (item?.allowed) return;
      const measure = Number(item?.measure);
      if (!Number.isFinite(measure)) return;
      const dynName = item?.dynamic;
      const fallback = dynName
        ? `${dynName} not common for this grade`
        : "Dynamic not common for this grade";
      const comment =
        dynName && commentMap?.[dynName] ? commentMap[dynName] : fallback;
      addMeasureIssue(index, measure, part, "dynamics", comment);
      measures.add(measure);
    });
  });

  return { index, measures };
}

function renderMeasureDetails(measure) {
  const detailsPane = document.getElementsByClassName("detail-body")[0];
  if (!detailsPane) return;
  detailsPane.innerHTML = "";
  detailsPane.classList.add("detail-body--measure");
  detailsPane.classList.remove(
    "detail-body--analyzer",
    "detail-body--global",
    "detail-body--list",
  );

  const header = document.createElement("div");
  header.className = "detail-header";

  const headerRow = document.createElement("div");
  headerRow.className = "detail-header-row";

  const backBtn = document.createElement("button");
  backBtn.type = "button";
  backBtn.className = "detail-back";
  backBtn.textContent = "Back";
  backBtn.addEventListener("click", () => handleDetailBack());

  const title = document.createElement("div");
  title.className = "detail-title";
  title.textContent = `@ m. ${measure}`;

  headerRow.appendChild(backBtn);
  headerRow.appendChild(title);
  header.appendChild(headerRow);
  detailsPane.appendChild(header);

  const index = window._measureIssueIndex || {};
  const entry = index[String(measure)];
  if (!entry || Object.keys(entry).length === 0) {
    const empty = document.createElement("div");
    empty.className = "measure-empty";
    empty.textContent = "No issues detected for this measure.";
    detailsPane.appendChild(empty);
    return;
  }

  const partNames = Object.keys(entry).sort((a, b) =>
    a.localeCompare(b, undefined, { sensitivity: "base" }),
  );
  partNames.forEach((part) => {
    const section = document.createElement("div");
    section.className = "measure-part";

    const heading = document.createElement("div");
    heading.className = "measure-part-title";
    heading.textContent = part;
    section.appendChild(heading);

    const analyzers = entry[part] || {};
    Object.keys(analyzers)
      .sort((a, b) => a.localeCompare(b))
      .forEach((analyzer) => {
        const comments = analyzers[analyzer] || [];
        if (comments.length === 0) return;
        const label = analyzer.charAt(0).toUpperCase() + analyzer.slice(1);
        const analyzerBlock = document.createElement("div");
        analyzerBlock.className = "measure-analyzer";

        const analyzerTitle = document.createElement("div");
        analyzerTitle.className = "measure-analyzer-title";
        analyzerTitle.textContent = label;
        analyzerBlock.appendChild(analyzerTitle);

        const beatGroups = new Map();
        const general = [];
        comments.forEach((comment) => {
          const match = String(comment).match(/^On beat\s+(\d+):\s*(.*)$/i);
          if (match) {
            const beatNum = Number(match[1]);
            const text = (match[2] || "").trim();
            if (!Number.isFinite(beatNum)) {
              if (text) general.push(text);
              return;
            }
            if (!beatGroups.has(beatNum)) beatGroups.set(beatNum, []);
            if (text) beatGroups.get(beatNum).push(text);
          } else {
            general.push(String(comment));
          }
        });

        const beatNums = [...beatGroups.keys()].sort((a, b) => a - b);
        beatNums.forEach((beatNum) => {
          const beatTitle = document.createElement("div");
          beatTitle.className = "measure-beat-title";
          beatTitle.textContent = `On beat ${beatNum}`;
          analyzerBlock.appendChild(beatTitle);

          const list = document.createElement("ul");
          list.className = "measure-issue-list";
          beatGroups.get(beatNum).forEach((comment) => {
            const item = document.createElement("li");
            item.className = "measure-issue-item";
            item.textContent = comment;
            list.appendChild(item);
          });
          analyzerBlock.appendChild(list);
        });

        if (general.length > 0) {
          const list = document.createElement("ul");
          list.className = "measure-issue-list";
          general.forEach((comment) => {
            const item = document.createElement("li");
            item.className = "measure-issue-item";
            item.textContent = comment;
            list.appendChild(item);
          });
          analyzerBlock.appendChild(list);
        }

        section.appendChild(analyzerBlock);
      });
    detailsPane.appendChild(section);
  });
}

const STRING_INSTRUMENT_PATTERNS = [
  /\bviolin(s)?\b/i,
  /\bviola(s)?\b/i,
  /\bvioloncello\b/i,
  /\bcello(s)?\b/i,
  /\bdouble\s+bass\b/i,
  /\bstring\s+bass\b/i,
  /\bupright\s+bass\b/i,
  /\bbass\s*viol\b/i,
  /\bharp\b/i,
  /\bguitar\b/i,
  /\bstrings?\b/i,
];

const STRING_INSTRUMENT_EXCLUDE = [
  /\bcontrabassoon\b/i,
  /\bcontra\s*bassoon\b/i,
  /\bcontrabass\s+clarinet\b/i,
  /\bcontra\s*bass\s+clarinet\b/i,
  /\bcontrabass\s+saxophone\b/i,
  /\bcontra\s*bass\s+saxophone\b/i,
  /\bcontrabass\s+trombone\b/i,
  /\bcontra\s*bass\s+trombone\b/i,
];

function extractInstrumentNames(text) {
  if (!text) return [];
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(text, "application/xml");
    if (doc.getElementsByTagName("parsererror")[0]) return [];

    const tags = ["part-name", "instrument-name", "instrName", "label"];
    const names = [];
    tags.forEach((tag) => {
      const nodes = doc.getElementsByTagName(tag);
      for (const node of nodes) {
        const value = node?.textContent?.trim();
        if (value) names.push(value);
      }
    });
    return names;
  } catch {
    return [];
  }
}

function detectStringInstruments(scoreText) {
  if (!scoreText) return [];
  const names = extractInstrumentNames(scoreText);
  const detected = names.filter((name) => {
    const text = String(name || "");
    if (STRING_INSTRUMENT_EXCLUDE.some((pattern) => pattern.test(text))) {
      return false;
    }
    return STRING_INSTRUMENT_PATTERNS.some((pattern) => pattern.test(text));
  });
  if (detected.length > 0) return [...new Set(detected)];
  const haystack = (names.length ? names.join(" ") : scoreText).toLowerCase();
  if (
    STRING_INSTRUMENT_PATTERNS.some((pattern) => pattern.test(haystack)) &&
    !STRING_INSTRUMENT_EXCLUDE.some((pattern) => pattern.test(haystack))
  ) {
    return ["String part(s) detected"];
  }
  return [];
}

function setKeyAnalysisMode(mode, opts = {}) {
  const normalized =
    mode === KEY_ANALYSIS_MODES.STRING
      ? KEY_ANALYSIS_MODES.STRING
      : KEY_ANALYSIS_MODES.STANDARD;
  window._keyAnalysisMode = normalized;
  if (opts.userChoice) {
    window._keyAnalysisUserChoice = true;
  }
  updateKeyAnalysisButton();
}

function updateKeyAnalysisButton() {
  const btn = document.getElementById("keyAnalysisBtn");
  if (!btn) return;
  const mode = window._keyAnalysisMode || KEY_ANALYSIS_MODES.STANDARD;
  const label =
    mode === KEY_ANALYSIS_MODES.STRING
      ? "String Key Analysis"
      : "Standard Key Analysis";
  btn.textContent = `Key Analysis: ${label}`;
}

function setObservedGrade(value, range) {
  const el = document.getElementById("observedGradeValue");
  if (!el) return;
  if (Array.isArray(range) && range.length === 2) {
    const low = Number(range[0]);
    const high = Number(range[1]);
    if (Number.isFinite(low) && Number.isFinite(high)) {
      el.textContent =
        low === high
          ? formatGrade(low)
          : `${formatGrade(low)}–${formatGrade(high)}`;
      return;
    }
  }
  if (value == null || !Number.isFinite(Number(value))) {
    el.textContent = "--";
    return;
  }
  el.textContent = formatGrade(value);
}

function openKeyAnalysisModal() {
  const modalEl = document.getElementById("keyAnalysisModal");
  if (!modalEl) return;
  modalEl.classList.add("key-analysis-modal");
  const labelEl = document.getElementById("keyAnalysisDetectedLabel");
  const descEl = document.getElementById("keyAnalysisDetectedDesc");
  const listEl = document.getElementById("keyAnalysisDetectedList");
  const hasStrings = Boolean(window._keyAnalysisHasStrings);
  const detected = window._keyAnalysisDetected || [];
  if (labelEl) {
    labelEl.textContent = hasStrings
      ? "String instruments detected"
      : "No string instruments detected";
  }
  if (descEl) {
    descEl.textContent = hasStrings
      ? "This score includes one or more string parts (e.g., violin/viola/cello/bass). String players typically prefer sharp-based keys over equivalent flat keys, so your key analysis can be interpreted in two ways:"
      : "This score does not appear to include string parts, but you can still choose how key spellings are interpreted for this analysis.";
  }
  if (listEl) {
    listEl.innerHTML = "";
    if (hasStrings && detected.length > 0) {
      const list = document.createElement("ul");
      detected.forEach((name) => {
        const item = document.createElement("li");
        item.textContent = name;
        list.appendChild(item);
      });
      listEl.appendChild(list);
    }
  }
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

function setTooltipTitle(el, title) {
  if (!el) return;
  el.setAttribute("title", title);
  el.setAttribute("data-bs-original-title", title);
  const tooltip = bootstrap.Tooltip.getInstance(el);
  if (tooltip && typeof tooltip.setContent === "function") {
    tooltip.setContent({ ".tooltip-inner": title });
  }
}

function countPartAnalyzerIssues(analyzer, payload) {
  if (!payload || typeof payload === "string") return 0;
  if (Array.isArray(payload)) return payload.length;
  if (typeof payload !== "object") return 0;

  const sumList = (list) => (Array.isArray(list) ? list.length : 0);
  const sumObjectValues = (obj, fn) =>
    Object.values(obj || {}).reduce((total, value) => total + fn(value), 0);

  switch (analyzer) {
    case "availability":
      return Object.keys(payload).length;
    case "dynamics":
      return sumObjectValues(payload, (part) => {
        const dynamicsCount = sumList(part?.dynamics);
        const commentsCount =
          part?.comments && typeof part.comments === "object"
            ? Object.keys(part.comments).length
            : 0;
        return dynamicsCount + commentsCount;
      });
    case "range":
      return sumObjectValues(payload, (part) => sumList(part?.["Note Data"]));
    case "articulation":
      return sumObjectValues(payload, (part) =>
        sumList(part?.articulation_data),
      );
    case "rhythm":
      return sumObjectValues(
        payload,
        (part) => sumList(part?.note_data) + sumList(part?.extreme_measures),
      );
    default:
      return 0;
  }
}

function updatePartAnalyzerIssueTooltips(filteredNotes) {
  const rows = [...document.querySelectorAll(".bar-row")];
  rows.forEach((row) => {
    const label = row
      .querySelector(".bar-head span")
      ?.textContent?.trim()
      .toLowerCase();
    if (!label || !PART_ANALYZERS.includes(label)) return;

    const button = row.querySelector(".details-mini");
    if (!button) return;

    const payload = filteredNotes?.[label];
    const count = countPartAnalyzerIssues(label, payload);
    const baseTitle =
      button.dataset.baseTitle ||
      button.getAttribute("data-bs-original-title") ||
      button.getAttribute("title") ||
      "";
    if (!button.dataset.baseTitle) {
      button.dataset.baseTitle = baseTitle;
    }
    const countText = `${count} issues found`;
    const newTitle = baseTitle ? `${baseTitle} (${countText})` : countText;
    setTooltipTitle(button, newTitle);
  });
}

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
  let tickList = Array.isArray(ticks) ? [...ticks] : [];
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
    const hasIssue = Boolean(tick.issue);
    tickEl.className = `timeline-tick${isStart ? " timeline-tick-start" : ""}${isEnd ? " timeline-tick-end" : ""}`;
    if (hasIssue) tickEl.classList.add("timeline-tick-issue");
    tickEl.style.left = `${Math.max(0, Math.min(100, left))}%`;

    const hasMeter = Boolean(tick.meter);
    const hasTempo = tick.tempo_bpm != null || tick.tempo;
    const hasKey = Boolean(tick.key);
    const issueOnly = hasIssue && !hasMeter && !hasTempo && !hasKey;
    if (issueOnly) tickEl.classList.add("timeline-tick-issue-only");
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

    if (!isStart && !isEnd) {
      const measureEl = document.createElement("button");
      measureEl.type = "button";
      measureEl.className = "tick-measure";
      if (hasIssue) measureEl.classList.add("tick-measure-issue");
      measureEl.dataset.measure = String(measure);
      measureEl.textContent = String(measure);
      measureEl.addEventListener("click", (evt) => {
        evt.stopPropagation();
        renderMeasureDetails(measure);
      });
      tickEl.appendChild(measureEl);
    }

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

  if (
    typeof data === "object" &&
    data !== null &&
    Array.isArray(data.segments)
  ) {
    return data.segments.map((x) => x.measure).filter(Number.isFinite);
  }

  if (typeof data === "object" && data !== null && "measure" in data) {
    return Number.isFinite(data.measure) ? [data.measure] : [];
  }

  return Object.values(data)
    .map((x) => x?.measure)
    .filter(Number.isFinite);
}

function prepareTimelineTicks() {
  const analysisData = window.analysisResult?.result;
  const filteredNotes = analysisData?.analysis_notes_filtered || {};
  const notes = analysisData?.analysis_notes || {};
  const keyPayload = notes.key || {};
  const keyData = Array.isArray(keyPayload)
    ? keyPayload
    : Array.isArray(keyPayload.segments)
      ? keyPayload.segments
      : Object.values(keyPayload);
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

  const issueMeta = buildMeasureIssueIndex(filteredNotes);
  window._measureIssueIndex = issueMeta.index;
  window._issueMeasures = issueMeta.measures;
  issueMeta.measures.forEach((measure) => {
    upsert(measure, { issue: true });
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
  if (startEl) startEl.textContent = durationCheck?.checked ? '0"' : "1";
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

window.prepareTimelineTicks = prepareTimelineTicks;

function rebuildTimelineFromCache() {
  const track = document.getElementById("timelineTrack");
  const meta = window._timelineMeta || {};
  const ticks = window._timelineTicks;
  if (!track || !Array.isArray(ticks)) return;
  buildTimelineTicks(track, ticks, meta.totalMeasures);
  setTimelineLabels(meta.totalMeasures, meta.durationString, meta.tempoData);
}

function bindBarHeadDetailPaneClicks() {
  // Prevent double-binding if user runs analysis multiple times
  if (window.__barHeadClicksBound) return;
  window.__barHeadClicksBound = true;

  const rows = document.getElementsByClassName("bar-head");
  Object.values(rows).forEach((row) => {
    row.addEventListener("click", () => {
      const filtered = window.analysisResult?.result?.analysis_notes_filtered;

      const detailsPane = document.getElementsByClassName("detail-body")[0];
      if (!detailsPane) return;

      detailsPane.innerHTML = "";
      detailsPane.classList.remove(
        "detail-body--measure",
        "detail-body--analyzer",
      );

      const analyzer = row
        .getElementsByTagName("span")[0]
        ?.textContent?.toLowerCase()
        ?.trim();

      if (!analyzer) return;

      const payload = filtered?.[analyzer];

      if (analyzer === "scoring") {
        renderScoringDetails(payload);
        return;
      }

      if (analyzer === "availability") {
        renderAvailabilityDetails(payload);
        return;
      }

      if (!PART_ANALYZERS.includes(analyzer)) {
        renderGlobalAnalyzerDetails(analyzer, payload);
        return;
      }

      // Case 1: Backend returned an instrument->something object
      // (and it has at least one key)
      if (payload && typeof payload === "object" && !Array.isArray(payload)) {
        if (Object.keys(payload).length > 0) {
          renderAnalyzerInstrumentList(analyzer, payload);
          return; // ✅ done
        }
      }

      // Case 2: Anything else (string message, empty object, null, array, etc.)
      // Render backend's message as text.
      // If it's an object/array, stringify so you don't get [object Object]
      if (typeof payload === "string") {
        detailsPane.textContent = payload;
      } else if (payload == null) {
        detailsPane.textContent = ""; // or "—"
      } else {
        detailsPane.textContent =
          typeof payload === "object"
            ? JSON.stringify(payload, null, 2)
            : String(payload);
      }
    });
  });
}

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
  const observedGrades = opts.observedGrades || {};
  const targetGrade =
    opts.targetGrade == null ? null : Number(opts.targetGrade);
  const showObserved =
    opts.showObserved == null ? true : Boolean(opts.showObserved);
  const availabilityNotes = opts.availabilityNotes || null;
  const labelMap = {
    availability: "Availability",
    dynamics: "Dynamics",
    scoring: "Scoring",
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
    let effectiveValue = value;
    if (effectiveValue == null && key === "availability") {
      effectiveValue = deriveAvailabilityConfidence(availabilityNotes);
    }
    const marker = getMarkerByLabel(label);
    if (!marker) return;
    const clamped =
      effectiveValue == null ? 0 : Math.max(0, Math.min(0.99, effectiveValue));
    marker.style.left = `${clamped * 100}%`;
    const scoreEl = document.querySelector(`[data-bar-score="${key}"]`);
    if (scoreEl) {
      if (effectiveValue == null) {
        scoreEl.textContent = emptyLabel;
      } else {
        const pct = Math.round(effectiveValue * 100);
        if (showObserved) {
          const observedRaw = observedGrades?.[key];
          const observedNum = observedRaw == null ? null : Number(observedRaw);
          const observedText = Number.isFinite(observedNum)
            ? formatGrade(observedNum)
            : "";
          scoreEl.textContent = observedText
            ? `${pct}% (${observedText})`
            : `${pct}%`;
          scoreEl.classList.toggle(
            "is-high",
            Number.isFinite(observedNum) &&
              Number.isFinite(targetGrade) &&
              observedNum > targetGrade,
          );
        } else {
          scoreEl.textContent = `${pct}%`;
          scoreEl.classList.remove("is-high");
        }
      }
      if (effectiveValue == null) {
        scoreEl.classList.remove("is-high");
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
  const configuredBase = String(
    window.SCORE_ANALYZER_API_BASE ||
      document.querySelector('meta[name="score-analyzer-api"]')?.content ||
      "",
  ).trim();
  const API_BASE = configuredBase
    ? configuredBase.replace(/\/+$/, "")
    : window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
      ? "http://127.0.0.1:5000"
      : "";
  console.log("API_BASE =", API_BASE);
  window.analysisResult = null;
  const analyzeBtn = document.getElementById("analyzeBtn");
  const targetOnly = document.getElementById("targetOnly");
  const fullGrade = document.getElementById("fullGradeSearch");
  const targetGrade = document.getElementById("targetGradeSelect");
  const keyAnalysisBtn = document.getElementById("keyAnalysisBtn");
  const keyAnalysisStringBtn = document.getElementById("keyAnalysisStringBtn");
  const keyAnalysisStandardBtn = document.getElementById(
    "keyAnalysisStandardBtn",
  );
  const modalEl = document.getElementById("progressModal");
  const progressBars = document.getElementById("progressBars");
  const progressText = document.getElementById("progressText");
  const progressOkBtn = document.getElementById("progressOkBtn");
  const progressTimer = document.getElementById("progressTimer");
  const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

  if (!analyzeBtn) return;

  if (!window._keyAnalysisMode) {
    window._keyAnalysisMode = KEY_ANALYSIS_MODES.STANDARD;
  }
  window._keyAnalysisUserChoice = false;
  window._keyAnalysisHasStrings = false;
  updateKeyAnalysisButton();

  if (keyAnalysisBtn) {
    keyAnalysisBtn.addEventListener("click", () => openKeyAnalysisModal());
  }
  if (keyAnalysisStringBtn) {
    keyAnalysisStringBtn.addEventListener("click", () => {
      setKeyAnalysisMode(KEY_ANALYSIS_MODES.STRING, { userChoice: true });
      const modalEl = document.getElementById("keyAnalysisModal");
      const modal = modalEl ? bootstrap.Modal.getInstance(modalEl) : null;
      modal?.hide();
    });
  }
  if (keyAnalysisStandardBtn) {
    keyAnalysisStandardBtn.addEventListener("click", () => {
      setKeyAnalysisMode(KEY_ANALYSIS_MODES.STANDARD, { userChoice: true });
      const modalEl = document.getElementById("keyAnalysisModal");
      const modal = modalEl ? bootstrap.Modal.getInstance(modalEl) : null;
      modal?.hide();
    });
  }

  if (progressOkBtn) {
    progressOkBtn.addEventListener("click", () => {
      // Just close modal; do NOT clear/rebuild timeline here.

      if (!window.analysisResult) return;

      const totalMeasures = window.analysisResult?.result?.total_measures ?? 0;
      const durationString = window.analysisResult?.result?.duration ?? 0;
      const tempoData =
        window.analysisResult?.result?.analysis_notes?.tempo ?? [];
      const targetGradeValue = Number(targetGrade?.value ?? NaN);
      setMarkerPositions(window.analysisResult?.result?.confidences, {
        observedGrades: window.analysisResult?.result?.observed_grades,
        targetGrade: targetGradeValue,
        showObserved: !targetOnly?.checked,
        availabilityNotes:
          window.analysisResult?.result?.analysis_notes?.availability,
      });
      setObservedGrade(
        window.analysisResult?.result?.observed_grade_overall,
        window.analysisResult?.result?.observed_grade_overall_range,
      );
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
    scoring: "Scoring",
    tempo: "Tempo",
    duration: "Duration",
    meter: "Meter",
  };

  const iconMap = {
    scoring: "icons/scoring.svg",
    range: "icons/range.svg",
    key: "icons/key.svg",
    articulation: "icons/articulation.svg",
    rhythm: "icons/rhythm.svg",
    dynamics: "icons/dynamic.svg",
    availability: "icons/instrument.svg",
    tempo: "icons/tempo.svg",
    duration: "icons/duration.svg",
    meter: "icons/meter.svg",
  };

  const colorMap = {
    scoring: "teal",
    range: "red",
    key: "orange",
    articulation: "light-green",
    rhythm: "pink",
    dynamics: "yellow",
    availability: "green",
    tempo: "blue",
    duration: "indigo",
    meter: "brown",
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
      const headLabelWrap = document.createElement("div");
      headLabelWrap.className = "progress-label";
      const headLabel = document.createElement("span");
      headLabel.className = "label";
      headLabel.id = barIds[key].label;
      headLabel.textContent = label;
      headLabelWrap.appendChild(headLabel);
      if (iconMap[key]) {
        const icon = document.createElement("img");
        icon.className = "progress-icon";
        icon.src = iconMap[key];
        icon.alt = `${label} icon`;
        headLabelWrap.appendChild(icon);
      }
      const pct = document.createElement("div");
      pct.className = "progress-percent";
      pct.id = barIds[key].pct;
      pct.textContent = "0%";
      head.appendChild(headLabelWrap);
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
    if (!API_BASE) {
      alert(
        "Missing backend URL. Set SCORE_ANALYZER_API_BASE in html/config.js (or a score-analyzer-api meta tag).",
      );
      return;
    }
    const fileInput = document.getElementById("fileInput");
    const file = fileInput?.files?.[0];
    if (!file) {
      alert("Please choose a score file.");
      return;
    }

    const form = new FormData();
    form.append("score_file", file);
    form.append("target_only", String(Boolean(targetOnly?.checked)));
    form.append(
      "strings_only",
      String(window._keyAnalysisMode === KEY_ANALYSIS_MODES.STRING),
    );
    form.append("full_grade_analysis", String(Boolean(fullGrade?.checked)));
    form.append("target_grade", String(Number(targetGrade?.value || 2)));
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
        progressTimer.textContent = `Time Elapsed - ${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      }, 200);
    }

    const applyFinalResult = (result) => {
      window.analysisResult = result;

      bindBarHeadDetailPaneClicks();
      updatePartAnalyzerIssueTooltips(
        result?.result?.analysis_notes_filtered,
      );
      const targetGradeValue = Number(targetGrade?.value ?? NaN);
      setMarkerPositions(result?.result?.confidences, {
        observedGrades: result?.result?.observed_grades,
        targetGrade: targetGradeValue,
        showObserved: !targetOnly?.checked,
        availabilityNotes: result?.result?.analysis_notes?.availability,
      });
      setObservedGrade(
        result?.result?.observed_grade_overall,
        result?.result?.observed_grade_overall_range,
      );
      const scoringPayload =
        result?.result?.analysis_notes_filtered?.scoring ??
        result?.result?.analysis_notes?.scoring;
      if (scoringPayload) {
        renderScoringDetails(scoringPayload);
      }

      const totalMeasures = result?.result?.total_measures ?? 0;
      const durationString = result?.result?.duration ?? 0;
      const tempoData = result?.result?.analysis_notes?.tempo ?? [];

      setTimelineLabels(totalMeasures, durationString, tempoData);

      const ticks = prepareTimelineTicks();
      console.log("ticks:", ticks);
      const track = document.getElementById("timelineTrack");
      window._timelineTicks = ticks;

      buildTimelineTicks(track, ticks, totalMeasures);
    };

    const handleEvent = (data) => {
      if (!data || data.type === "heartbeat") return;
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
          progressText.textContent = `${name} grade ${formatGrade(data.grade)} - ${pct}%`;
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
          const tempoBar = tempoIds ? document.getElementById(tempoIds.bar) : null;
          const tempoPct = tempoIds ? document.getElementById(tempoIds.pct) : null;
          const durationBar = durationIds ? document.getElementById(durationIds.bar) : null;
          const durationPct = durationIds ? document.getElementById(durationIds.pct) : null;
          if (tempoBar) tempoBar.style.width = "100%";
          if (tempoPct) tempoPct.textContent = "100%";
          if (durationBar) durationBar.style.width = "100%";
          if (durationPct) durationPct.textContent = "100%";
        }
      } else if (data.type === "timeout") {
        if (progressText) {
          progressText.textContent = "Timed out. Showing partial results.";
        }
      } else if (data.type === "result") {
        applyFinalResult({ done: true, error: null, result: data.data });
      } else if (data.type === "error") {
        if (progressText) progressText.textContent = "Analysis error.";
        console.error("Analysis error:", data.error);
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
      }
    };

    let gotResult = false;
    const handleEventWithResult = (data) => {
      if (data?.type === "result") {
        gotResult = true;
      }
      handleEvent(data);
    };

    try {
      const res = await fetch(`${API_BASE}/api/analyze_stream`, {
        method: "POST",
        body: form,
        headers: {
          Accept: "text/event-stream",
        },
      });

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "Failed to start analysis.");
        if (timerId) clearInterval(timerId);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          if (!chunk) continue;
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            const payload = line.slice(5).trim();
            if (!payload) continue;
            try {
              const data = JSON.parse(payload);
              handleEventWithResult(data);
            } catch (err) {
              console.warn("Failed to parse SSE payload:", payload, err);
            }
          }
        }
      }

      if (!gotResult) {
        console.warn("Stream ended without result event.");
        if (progressText) progressText.textContent = "Connection lost.";
        if (timerId) clearInterval(timerId);
        if (progressOkBtn) progressOkBtn.disabled = false;
      }
    } catch (err) {
      console.error("Failed to stream analysis:", err);
      if (progressText) progressText.textContent = "Connection lost.";
      if (timerId) clearInterval(timerId);
      if (progressOkBtn) progressOkBtn.disabled = false;
    }
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

  const issueToggle = document.getElementById("toggleIssueMeasures");
  if (issueToggle) {
    const syncIssue = () => {
      timeline.classList.toggle("show-issue-measures", issueToggle.checked);
    };
    issueToggle.addEventListener("change", syncIssue);
    syncIssue();
  }

  bind("toggleKey", "hide-key");
  bind("toggleTempo", "hide-tempo");
  bind("toggleMeter", "hide-meter");

  const durationToggle = document.getElementById("toggleDuration");
  if (durationToggle) {
    durationToggle.addEventListener("change", () => {
      const meta = window._timelineMeta || {};
      setTimelineLabels(
        meta.totalMeasures,
        meta.durationString,
        meta.tempoData,
      );
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
    defaultView: "responsive",
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
  const controlsEl = document.querySelector(".controls");
  const loadLabel = document.querySelector(".score-load");
  const clearButton = document.querySelector(".score-clear");
  const scoreActions = document.querySelectorAll(".score-action");
  const targetOnlyToggle = document.getElementById("targetOnly");
  const observedPane = document.getElementById("observedGradePane");

  let hasActiveScore = false;

  const syncScoreActions = () => {
    if (controlsEl) {
      controlsEl.classList.toggle("has-score", hasActiveScore);
    }
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
      window._keyAnalysisDetected = detectStringInstruments(text);
      window._keyAnalysisHasStrings = window._keyAnalysisDetected.length > 0;
      window._keyAnalysisUserChoice = false;
      setKeyAnalysisMode(
        window._keyAnalysisHasStrings
          ? KEY_ANALYSIS_MODES.STRING
          : KEY_ANALYSIS_MODES.STANDARD,
      );
      if (window._keyAnalysisHasStrings) {
        openKeyAnalysisModal();
      }
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
    const detailsPane = document.getElementsByClassName("detail-body")[0];
    if (fileInput) fileInput.value = "";
    if (titleEl) titleEl.textContent = "Score Title: --";

    appEl.innerHTML = "";
    app = new window.Verovio.App(appEl, {
      defaultView: "responsive",
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
        scoring: null,
      },
      { emptyLabel: "--" },
    );

    const track = document.getElementById("timelineTrack");
    if (track) {
      track.querySelectorAll(".timeline-tick").forEach((node) => node.remove());
    }
    if (detailsPane) {
      detailsPane.innerHTML = "";
      detailsPane.classList.remove(
        "detail-body--measure",
        "detail-body--analyzer",
        "detail-body--global",
        "detail-body--list",
      );
    }
    setTimelineLabels();
    updatePartAnalyzerIssueTooltips(null);
    setObservedGrade(null);
  });

  zoomApply?.addEventListener("click", () =>
    setCssZoomPercent(Number(zoomInput?.value || 100)),
  );
  zoomInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") setCssZoomPercent(Number(zoomInput.value || 100));
  });

  syncScoreActions();
}

function initTimelineResize() {
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      rebuildTimelineFromCache();
    }, 150);
  });
}

function initExportControls() {
  const exportBtn = document.getElementById("exportBtn");
  const modalEl = document.getElementById("exportModal");
  const visibleBtn = document.getElementById("exportVisibleBtn");
  const allBtn = document.getElementById("exportAllBtn");
  const progressWrap = document.getElementById("exportProgress");
  const progressBar = document.getElementById("exportProgressBar");
  const statusEl = document.getElementById("exportStatus");
  const modal = modalEl ? new bootstrap.Modal(modalEl) : null;

  if (!exportBtn || !modalEl) return;

  const setProgress = (pct, text) => {
    if (progressBar) {
      progressBar.style.width = `${pct}%`;
      progressBar.textContent = `${pct}%`;
    }
    if (statusEl && text) statusEl.textContent = text;
  };

  const getBaseFilename = () => {
    const title =
      document.getElementById("scoreTitle")?.textContent || "analysis";
    const cleaned = title.replace(/Score Title:\s*/i, "").trim();
    return cleaned || "analysis";
  };

  const buildDetailsCsv = () => {
    const pane = document.querySelector(".detail-body");
    const lines = pane
      ? pane.innerText
          .split(/\n+/)
          .map((l) => l.trim())
          .filter(Boolean)
      : [];
    const rows = [
      "line",
      ...lines.map((line) => `"${line.replace(/"/g, '""')}"`),
    ];
    return new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  };

  const buildFullAnalysis = () => {
    const payload = window.analysisResult?.result ?? {};
    const json = JSON.stringify(payload, null, 2);
    return new Blob([json], { type: "application/json;charset=utf-8;" });
  };

  const runExport = (builder, filename) => {
    if (!window.analysisResult?.result) {
      alert("Please run analysis before exporting.");
      return;
    }
    if (progressWrap) progressWrap.hidden = false;
    if (visibleBtn) visibleBtn.disabled = true;
    if (allBtn) allBtn.disabled = true;
    setProgress(0, "Preparing file...");

    let pct = 0;
    const timer = setInterval(() => {
      pct = Math.min(90, pct + 5);
      setProgress(pct, "Preparing file...");
    }, 120);

    setTimeout(() => {
      const blob = builder();
      clearInterval(timer);
      setProgress(100, "Ready to save.");
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (visibleBtn) visibleBtn.disabled = false;
      if (allBtn) allBtn.disabled = false;
    }, 250);
  };

  exportBtn.addEventListener("click", () => {
    if (progressWrap) progressWrap.hidden = true;
    setProgress(0, "Preparing file...");
    modal?.show();
  });

  visibleBtn?.addEventListener("click", () => {
    const name = `${getBaseFilename()}_details.csv`;
    runExport(buildDetailsCsv, name);
  });

  allBtn?.addEventListener("click", () => {
    const name = `${getBaseFilename()}_analysis.json`;
    runExport(buildFullAnalysis, name);
  });
}

// Run immediately (DOM is already present because your script tag is at the bottom)
initTooltips();
initGradeOptions();
initAnalysisRequest();
initTimelineToggles();
initTimelineResize();
initExportControls();
initVerovio().catch((err) => console.error("initVerovio failed:", err));
setTimelineLabels();
