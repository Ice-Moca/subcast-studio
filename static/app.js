// SUBCAST STUDIO (Nord Edition) - Client Logic

const state = {
  lines: [],
  customSpokenByLine: new Map(),
  selectedLineIndex: 0,
  fonts: [],
  loadedFontFaces: new Set(),
  sttSegments: [],
};

// DOM References
const tabButtons = document.querySelectorAll(".mode-tab");
const views = document.querySelectorAll(".workspace-view");

const scriptInput = document.getElementById("script-input");
const lineCountBadge = document.getElementById("line-count-badge");
const chkExcludeNumbers = document.getElementById("chk-exclude-numbers");
const chkExcludeSpecial = document.getElementById("chk-exclude-special");
const customExcludeInput = document.getElementById("custom-exclude-input");
const scriptDiffList = document.getElementById("script-diff-list");

const toggleNoVoice = document.getElementById("toggle-no-voice");
const pillVoiceOn = document.getElementById("pill-voice-on");
const pillVoiceOff = document.getElementById("pill-voice-off");
const enginePills = document.querySelectorAll(".engine-pill");
const noVoiceDurationBox = document.getElementById("no-voice-duration-box");
const lineDurationSlider = document.getElementById("line-duration-slider");
const valLineDuration = document.getElementById("val-line-duration");
const ttsControlsBody = document.getElementById("tts-controls-body");
const pronunciationFilterCard = document.getElementById("pronunciation-filter-card");
const previewVoiceBadge = document.getElementById("preview-voice-badge");
const btnRenderLabel = document.getElementById("btn-render-label");

const ttsEngineSelect = document.getElementById("tts-engine-select");
const typecastConfigBox = document.getElementById("typecast-config-box");
const edgeConfigBox = document.getElementById("edge-config-box");
const typecastApiKey = document.getElementById("typecast-api-key");
const typecastActorId = document.getElementById("typecast-actor-id");
const typecastEmotion = document.getElementById("typecast-emotion");
const btnFetchActors = document.getElementById("btn-fetch-actors");
const actorSelectWrap = document.getElementById("actor-select-wrap");
const typecastActorSelect = document.getElementById("typecast-actor-select");
const edgeVoiceSelect = document.getElementById("edge-voice-select");
const ttsSpeed = document.getElementById("tts-speed");
const valTtsSpeed = document.getElementById("val-tts-speed");
const ttsPause = document.getElementById("tts-pause");
const valTtsPause = document.getElementById("val-tts-pause");

const fontSelect = document.getElementById("font-select");
const fontUploadInput = document.getElementById("font-upload-input");
const fontSizeSlider = document.getElementById("font-size-slider");
const valFontSize = document.getElementById("val-font-size");
const subYSlider = document.getElementById("sub-y-slider");
const valSubY = document.getElementById("val-sub-y");

const textColorPicker = document.getElementById("text-color-picker");
const textColorHex = document.getElementById("text-color-hex");
const strokeColorPicker = document.getElementById("stroke-color-picker");
const strokeColorHex = document.getElementById("stroke-color-hex");
const strokeWidthSlider = document.getElementById("stroke-width-slider");
const valStrokeWidth = document.getElementById("val-stroke-width");

const chkShadowEnabled = document.getElementById("chk-shadow-enabled");
const shadowColorPicker = document.getElementById("shadow-color-picker");
const shadowColorHex = document.getElementById("shadow-color-hex");
const shadowOpacitySlider = document.getElementById("shadow-opacity-slider");
const valShadowOpacity = document.getElementById("val-shadow-opacity");
const shadowXSlider = document.getElementById("shadow-x-slider");
const valShadowX = document.getElementById("val-shadow-x");
const shadowYSlider = document.getElementById("shadow-y-slider");
const valShadowY = document.getElementById("val-shadow-y");
const shadowBlurSlider = document.getElementById("shadow-blur-slider");
const valShadowBlur = document.getElementById("val-shadow-blur");

const chkBgboxEnabled = document.getElementById("chk-bgbox-enabled");
const bgboxColorPicker = document.getElementById("bgbox-color-picker");
const bgboxColorHex = document.getElementById("bgbox-color-hex");
const bgboxOpacitySlider = document.getElementById("bgbox-opacity-slider");
const valBgboxOpacity = document.getElementById("val-bgbox-opacity");

const monitorStage = document.getElementById("monitor-stage");
const previewCanvas = document.getElementById("preview-canvas");
const previewLineIndicator = document.getElementById("preview-line-indicator");
const backdropBtns = document.querySelectorAll(".backdrop-btn");
const presetChips = document.querySelectorAll(".preset-chip");

const exportFormatSelect = document.getElementById("export-format-select");
const btnRenderVideo = document.getElementById("btn-render-video");
const renderProgressWrap = document.getElementById("render-progress-wrap");
const renderStatusMsg = document.getElementById("render-status-msg");
const renderResultCard = document.getElementById("render-result-card");
const renderDurationBadge = document.getElementById("render-duration-badge");
const renderedVideoPlayer = document.getElementById("rendered-video-player");
const renderDownloadLinks = document.getElementById("render-download-links");
const splitClipsList = document.getElementById("split-clips-list");

// STT References
const sttDropzone = document.getElementById("stt-dropzone");
const sttFileInput = document.getElementById("stt-file-input");
const sttVideoPreview = document.getElementById("stt-video-preview");
const sttLangSelect = document.getElementById("stt-lang-select");
const sttModelSelect = document.getElementById("stt-model-select");
const sttExcludeNumbers = document.getElementById("stt-exclude-numbers");
const sttExcludeSpecial = document.getElementById("stt-exclude-special");
const btnRunStt = document.getElementById("btn-run-stt");
const sttProgressWrap = document.getElementById("stt-progress-wrap");
const sttSegmentCount = document.getElementById("stt-segment-count");
const sttSegmentsList = document.getElementById("stt-segments-list");
const sttDownloadLinks = document.getElementById("stt-download-links");
const btnSendToTts = document.getElementById("btn-send-to-tts");
const btnSaveEditedSrt = document.getElementById("btn-save-edited-srt");

// Mode Switching
tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    views.forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    const target = document.getElementById(btn.dataset.target);
    if (target) target.classList.add("active");
  });
});

// Backdrop Switcher for 16:9 Monitor
backdropBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    backdropBtns.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    monitorStage.classList.remove("bg-checker", "bg-dark", "bg-green");
    monitorStage.classList.add(btn.dataset.bg);
  });
});

// "No Voice" Dev Guide Pill Toggle Handler
function syncNoVoiceUI() {
  const isNoVoice = toggleNoVoice.checked;
  const durSec = parseFloat(lineDurationSlider.value).toFixed(1);

  if (pillVoiceOn && pillVoiceOff) {
    pillVoiceOn.classList.toggle("active", !isNoVoice);
    pillVoiceOff.classList.toggle("active", isNoVoice);
    pillVoiceOff.querySelector("span").textContent = `음성 없음 (${durSec}초)`;
  }

  if (isNoVoice) {
    noVoiceDurationBox.style.display = "flex";
    ttsControlsBody.style.display = "none";
    pronunciationFilterCard.style.opacity = "0.45";
    previewVoiceBadge.textContent = `무음 · ${durSec}s`;
    previewVoiceBadge.classList.add("muted");
    btnRenderLabel.textContent = "무음 영상 생성";
  } else {
    noVoiceDurationBox.style.display = "none";
    ttsControlsBody.style.display = "flex";
    pronunciationFilterCard.style.opacity = "1";
    previewVoiceBadge.textContent = "TTS 활성";
    previewVoiceBadge.classList.remove("muted");
    btnRenderLabel.textContent = "영상 생성";
  }
  renderDiffList();
}

if (pillVoiceOn && pillVoiceOff) {
  pillVoiceOn.addEventListener("click", () => {
    toggleNoVoice.checked = false;
    syncNoVoiceUI();
  });
  pillVoiceOff.addEventListener("click", () => {
    toggleNoVoice.checked = true;
    syncNoVoiceUI();
  });
}

toggleNoVoice.addEventListener("change", syncNoVoiceUI);
lineDurationSlider.addEventListener("input", () => {
  valLineDuration.textContent = `${parseFloat(lineDurationSlider.value).toFixed(1)}s`;
  syncNoVoiceUI();
});

// Nord Style Quick Presets
const NORD_PRESETS = {
  snow: {
    textColor: "#ECEFF4",
    strokeColor: "#2E3440",
    strokeWidth: 4,
    shadowEnabled: true,
    shadowColor: "#2E3440",
    shadowOpacity: 80,
    bgBoxEnabled: false,
  },
  frost: {
    textColor: "#88C0D0",
    strokeColor: "#2E3440",
    strokeWidth: 5,
    shadowEnabled: true,
    shadowColor: "#242933",
    shadowOpacity: 85,
    bgBoxEnabled: false,
  },
  aurora: {
    textColor: "#EBCB8B",
    strokeColor: "#2E3440",
    strokeWidth: 5,
    shadowEnabled: true,
    shadowColor: "#2E3440",
    shadowOpacity: 85,
    bgBoxEnabled: false,
  },
  box: {
    textColor: "#ECEFF4",
    strokeColor: "#2E3440",
    strokeWidth: 0,
    shadowEnabled: false,
    shadowColor: "#2E3440",
    shadowOpacity: 60,
    bgBoxEnabled: true,
    bgBoxColor: "#2E3440",
    bgBoxOpacity: 78,
  },
};

presetChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const p = NORD_PRESETS[chip.dataset.preset];
    if (!p) return;
    textColorPicker.value = p.textColor;
    textColorHex.value = p.textColor;
    strokeColorPicker.value = p.strokeColor;
    strokeColorHex.value = p.strokeColor;
    strokeWidthSlider.value = p.strokeWidth;
    valStrokeWidth.textContent = `${p.strokeWidth}px`;
    chkShadowEnabled.checked = p.shadowEnabled;
    shadowColorPicker.value = p.shadowColor;
    shadowColorHex.value = p.shadowColor;
    shadowOpacitySlider.value = p.shadowOpacity;
    valShadowOpacity.textContent = `${p.shadowOpacity}%`;
    chkBgboxEnabled.checked = p.bgBoxEnabled;
    if (p.bgBoxColor) {
      bgboxColorPicker.value = p.bgBoxColor;
      bgboxColorHex.value = p.bgBoxColor;
    }
    if (p.bgBoxOpacity) {
      bgboxOpacitySlider.value = p.bgBoxOpacity;
      valBgboxOpacity.textContent = `${p.bgBoxOpacity}%`;
    }
    drawSubtitlePreview();
  });
});

// TTS Engine Pill Toggle (AI Proxy Dev Guide style)
function syncEngineUI(val) {
  ttsEngineSelect.value = val;
  enginePills.forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.engine === val);
  });
  typecastConfigBox.style.display = val === "typecast" ? "flex" : "none";
  edgeConfigBox.style.display = val === "edge" ? "flex" : "none";
}

enginePills.forEach((pill) => {
  pill.addEventListener("click", () => {
    syncEngineUI(pill.dataset.engine);
  });
});

ttsEngineSelect.addEventListener("change", () => {
  syncEngineUI(ttsEngineSelect.value);
});

// Persist Typecast API Key & Actor ID in localStorage for convenience
if (localStorage.getItem("typecast_api_key")) {
  typecastApiKey.value = localStorage.getItem("typecast_api_key");
}
if (localStorage.getItem("typecast_actor_id")) {
  typecastActorId.value = localStorage.getItem("typecast_actor_id");
}
typecastApiKey.addEventListener("input", () => {
  localStorage.setItem("typecast_api_key", typecastApiKey.value);
});
typecastActorId.addEventListener("input", () => {
  localStorage.setItem("typecast_actor_id", typecastActorId.value);
});

// Fetch Typecast Actors
btnFetchActors.addEventListener("click", async () => {
  const key = typecastApiKey.value.trim();
  if (!key) {
    alert("Typecast API Key를 먼저 입력해 주세요.");
    return;
  }
  btnFetchActors.disabled = true;
  btnFetchActors.textContent = "조회 중...";
  try {
    const res = await fetch("/api/typecast/actors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "성우 목록 조회 실패");
    typecastActorSelect.innerHTML = "";
    data.actors.forEach((a) => {
      const opt = document.createElement("option");
      opt.value = a.actor_id;
      opt.textContent = `${a.name} (${a.language}) — ${a.actor_id}`;
      typecastActorSelect.appendChild(opt);
    });
    if (data.actors.length > 0) {
      actorSelectWrap.style.display = "flex";
      typecastActorId.value = data.actors[0].actor_id;
      localStorage.setItem("typecast_actor_id", typecastActorId.value);
    }
  } catch (err) {
    alert(err.message);
  } finally {
    btnFetchActors.disabled = false;
    btnFetchActors.textContent = "내 성우 목록 조회";
  }
});

typecastActorSelect.addEventListener("change", () => {
  typecastActorId.value = typecastActorSelect.value;
  localStorage.setItem("typecast_actor_id", typecastActorId.value);
});

// Load Available Fonts & Register Custom FontFace in Browser
async function loadFontsList(selectIdAfter = null) {
  const res = await fetch("/api/fonts");
  const data = await res.json();
  state.fonts = data.fonts || [];
  fontSelect.innerHTML = "";

  for (const f of state.fonts) {
    const opt = document.createElement("option");
    opt.value = f.id;
    opt.textContent = f.name;
    fontSelect.appendChild(opt);

    if (f.url && !state.loadedFontFaces.has(f.id)) {
      try {
        const fontFace = new FontFace(`CustomFont_${f.id}`, `url(${encodeURI(f.url)})`);
        const loaded = await fontFace.load();
        document.fonts.add(loaded);
        state.loadedFontFaces.add(f.id);
      } catch (e) {
        console.warn("Font preview load error:", e);
      }
    }
  }

  if (selectIdAfter) {
    fontSelect.value = selectIdAfter;
  }
  drawSubtitlePreview();
}

fontUploadInput.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/fonts/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "폰트 업로드 실패");
    await loadFontsList(data.id);
  } catch (err) {
    alert(err.message);
  }
});

// Color Picker <-> Hex Input Sync
function bindColorPair(picker, hexInput) {
  picker.addEventListener("input", () => {
    hexInput.value = picker.value.toUpperCase();
    drawSubtitlePreview();
  });
  hexInput.addEventListener("input", () => {
    const val = hexInput.value.trim();
    if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
      picker.value = val;
      drawSubtitlePreview();
    }
  });
}

bindColorPair(textColorPicker, textColorHex);
bindColorPair(strokeColorPicker, strokeColorHex);
bindColorPair(shadowColorPicker, shadowColorHex);
bindColorPair(bgboxColorPicker, bgboxColorHex);

// Range Sliders Live Update
const sliderBindings = [
  [ttsSpeed, valTtsSpeed, (v) => `${parseFloat(v).toFixed(2)}x`],
  [ttsPause, valTtsPause, (v) => `${parseFloat(v).toFixed(2)}s`],
  [fontSizeSlider, valFontSize, (v) => `${v}px`],
  [subYSlider, valSubY, (v) => `${v}%`],
  [strokeWidthSlider, valStrokeWidth, (v) => `${v}px`],
  [shadowOpacitySlider, valShadowOpacity, (v) => `${v}%`],
  [shadowXSlider, valShadowX, (v) => `${v}px`],
  [shadowYSlider, valShadowY, (v) => `${v}px`],
  [shadowBlurSlider, valShadowBlur, (v) => `${v}px`],
  [bgboxOpacitySlider, valBgboxOpacity, (v) => `${v}%`],
];

sliderBindings.forEach(([slider, badge, fmt]) => {
  slider.addEventListener("input", () => {
    badge.textContent = fmt(slider.value);
    drawSubtitlePreview();
  });
});

[fontSelect, chkShadowEnabled, chkBgboxEnabled].forEach((el) => {
  el.addEventListener("change", drawSubtitlePreview);
});

// Update Script Lines & Spoken Text Sanitization Preview
let previewDebounce = null;
function scheduleScriptPreview() {
  clearTimeout(previewDebounce);
  previewDebounce = setTimeout(updateScriptLinesPreview, 120);
}

[scriptInput, chkExcludeNumbers, chkExcludeSpecial, customExcludeInput].forEach((el) => {
  el.addEventListener("input", scheduleScriptPreview);
  el.addEventListener("change", scheduleScriptPreview);
});

async function updateScriptLinesPreview() {
  try {
    const res = await fetch("/api/script/preview-lines", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        script: scriptInput.value,
        exclude_numbers: chkExcludeNumbers.checked,
        exclude_special: chkExcludeSpecial.checked,
        custom_exclude_chars: customExcludeInput.value,
      }),
    });
    const data = await res.json();
    state.lines = (data.lines || []).map((item) => {
      const autoSpoken = item.spoken_text;
      const hasCustom = state.customSpokenByLine.has(item.display_text);
      const finalSpoken = hasCustom
        ? state.customSpokenByLine.get(item.display_text)
        : autoSpoken;
      return {
        ...item,
        auto_spoken_text: autoSpoken,
        spoken_text: finalSpoken,
        custom_edited: hasCustom && finalSpoken !== autoSpoken,
      };
    });
    lineCountBadge.textContent = `${state.lines.length}줄`;

    if (state.selectedLineIndex >= state.lines.length) {
      state.selectedLineIndex = Math.max(0, state.lines.length - 1);
    }

    renderDiffList();
    drawSubtitlePreview();
  } catch (e) {
    console.error(e);
  }
}

function renderDiffList() {
  scriptDiffList.innerHTML = "";
  if (state.lines.length === 0) {
    scriptDiffList.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 10px 4px;">대본을 입력하세요.</div>`;
    return;
  }

  const isNoVoice = toggleNoVoice.checked;
  const durSec = parseFloat(lineDurationSlider.value).toFixed(1);

  state.lines.forEach((item, idx) => {
    const row = document.createElement("div");
    row.className = `diff-row ${idx === state.selectedLineIndex ? "active" : ""}`;

    const subInfoHtml = isNoVoice
      ? `<div class="diff-spoken">
           <span class="diff-badge silent-mode">무음 · ${durSec}s</span>
         </div>`
      : `<div class="diff-spoken">
           <span class="diff-badge ${item.custom_edited ? "edited" : ""}" data-badge-idx="${idx}">${item.custom_edited ? "TTS 수정" : "TTS"}</span>
           <input
             type="text"
             class="diff-spoken-input"
             value="${escapeHtml(item.spoken_text)}"
             placeholder="TTS로 읽을 대사 입력 (비우면 무음)"
             aria-label="#${item.index} TTS 발화 대사 수정"
           />
           <button
             type="button"
             class="diff-reset-btn"
             title="자동 발화 텍스트로 복원"
             style="display: ${item.custom_edited ? "inline-flex" : "none"};"
           >↺</button>
         </div>`;

    row.innerHTML = `
      <div class="diff-idx">#${item.index}</div>
      <div class="diff-content">
        <div class="diff-display">${escapeHtml(item.display_text)}</div>
        ${subInfoHtml}
      </div>
    `;

    const selectRow = () => {
      state.selectedLineIndex = idx;
      scriptDiffList.querySelectorAll(".diff-row").forEach((r, rIdx) => {
        r.classList.toggle("active", rIdx === idx);
      });
      drawSubtitlePreview();
    };

    row.addEventListener("click", selectRow);

    const spokenInput = row.querySelector(".diff-spoken-input");
    const badgeEl = row.querySelector("[data-badge-idx]");
    const resetBtn = row.querySelector(".diff-reset-btn");

    if (spokenInput) {
      spokenInput.addEventListener("click", (e) => {
        e.stopPropagation();
        selectRow();
      });

      spokenInput.addEventListener("input", (e) => {
        const val = e.target.value;
        item.spoken_text = val;
        if (val === item.auto_spoken_text) {
          state.customSpokenByLine.delete(item.display_text);
          item.custom_edited = false;
        } else {
          state.customSpokenByLine.set(item.display_text, val);
          item.custom_edited = true;
        }
        if (badgeEl) {
          badgeEl.textContent = item.custom_edited ? "TTS 수정" : "TTS";
          badgeEl.classList.toggle("edited", item.custom_edited);
        }
        if (resetBtn) {
          resetBtn.style.display = item.custom_edited ? "inline-flex" : "none";
        }
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        state.customSpokenByLine.delete(item.display_text);
        item.spoken_text = item.auto_spoken_text;
        item.custom_edited = false;
        if (spokenInput) spokenInput.value = item.auto_spoken_text;
        if (badgeEl) {
          badgeEl.textContent = "TTS";
          badgeEl.classList.remove("edited");
        }
        resetBtn.style.display = "none";
      });
    }

    scriptDiffList.appendChild(row);
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function parseApiJson(res, fallbackMsg = "요청 처리 중 오류가 발생했습니다.") {
  const rawText = await res.text();
  try {
    return JSON.parse(rawText);
  } catch (_) {
    throw new Error(`${fallbackMsg} (HTTP ${res.status}: ${rawText.slice(0, 120) || "서버 응답 오류"})`);
  }
}

function hexToRgbaCss(hex, opacity = 1.0) {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.substring(0, 2) || "00", 16);
  const g = parseInt(clean.substring(2, 4) || "00", 16);
  const b = parseInt(clean.substring(4, 6) || "00", 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

// Draw 1920x1080 16:9 Live Subtitle Preview on HTML5 Canvas
function drawSubtitlePreview() {
  const ctx = previewCanvas.getContext("2d");
  const W = previewCanvas.width;
  const H = previewCanvas.height;
  ctx.clearRect(0, 0, W, H);

  const activeItem = state.lines[state.selectedLineIndex];
  const text = activeItem ? activeItem.display_text : "자막 미리보기 텍스트입니다";
  previewLineIndicator.textContent = activeItem
    ? `LINE #${activeItem.index}`
    : "PREVIEW";

  if (!text.trim()) return;

  const fontId = fontSelect.value;
  const fontObj = state.fonts.find((f) => f.id === fontId);
  let fontFamily = `"Apple SD Gothic Neo", "AppleGothic", sans-serif`;
  if (fontObj && fontObj.is_custom && state.loadedFontFaces.has(fontId)) {
    fontFamily = `"CustomFont_${fontId}", "Apple SD Gothic Neo", sans-serif`;
  }

  const fontSize = parseInt(fontSizeSlider.value, 10) || 68;
  const yPct = parseFloat(subYSlider.value) || 84;
  const textColor = textColorPicker.value;
  const strokeColor = strokeColorPicker.value;
  const strokeWidth = parseInt(strokeWidthSlider.value, 10) || 0;

  const shadowEnabled = chkShadowEnabled.checked;
  const shadowColor = shadowColorPicker.value;
  const shadowOpacity = (parseInt(shadowOpacitySlider.value, 10) || 0) / 100.0;
  const shadowX = parseInt(shadowXSlider.value, 10) || 0;
  const shadowY = parseInt(shadowYSlider.value, 10) || 0;
  const shadowBlur = parseInt(shadowBlurSlider.value, 10) || 0;

  const bgBoxEnabled = chkBgboxEnabled.checked;
  const bgBoxColor = bgboxColorPicker.value;
  const bgBoxOpacity = (parseInt(bgboxOpacitySlider.value, 10) || 65) / 100.0;

  ctx.font = `600 ${fontSize}px ${fontFamily}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";

  // Word wrapping at 1640px max width
  const maxWidth = 1640;
  const wrappedLines = [];
  for (const rawLine of text.split("\n")) {
    const words = rawLine.split(" ");
    let current = "";
    for (const w of words) {
      const candidate = current ? `${current} ${w}` : w;
      if (ctx.measureText(candidate).width <= maxWidth) {
        current = candidate;
      } else {
        if (current) wrappedLines.push(current);
        current = w;
      }
    }
    if (current) wrappedLines.push(current);
  }

  const lineHeight = fontSize * 1.28;
  const totalHeight = wrappedLines.length * lineHeight;
  const centerX = W / 2;
  const centerY = H * (yPct / 100.0);

  let maxLineW = 0;
  wrappedLines.forEach((l) => {
    const m = ctx.measureText(l).width;
    if (m > maxLineW) maxLineW = m;
  });

  // 1. Optional Background Box
  if (bgBoxEnabled) {
    ctx.save();
    const padX = 32;
    const padY = 18;
    const boxW = maxLineW + padX * 2;
    const boxH = totalHeight + padY * 2;
    const boxX = centerX - boxW / 2;
    const boxY = centerY - boxH / 2;
    ctx.fillStyle = hexToRgbaCss(bgBoxColor, bgBoxOpacity);
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 14);
    ctx.fill();
    ctx.restore();
  }

  // Draw each line
  const startY = centerY - totalHeight / 2 + lineHeight / 2;

  wrappedLines.forEach((lineText, i) => {
    const ly = startY + i * lineHeight;

    // 2. Drop Shadow
    if (shadowEnabled && shadowOpacity > 0) {
      ctx.save();
      ctx.shadowColor = hexToRgbaCss(shadowColor, shadowOpacity);
      ctx.shadowOffsetX = shadowX;
      ctx.shadowOffsetY = shadowY;
      ctx.shadowBlur = shadowBlur * 1.6;
      ctx.fillStyle = hexToRgbaCss(shadowColor, shadowOpacity);
      if (strokeWidth > 0) {
        ctx.lineWidth = strokeWidth * 2;
        ctx.strokeStyle = hexToRgbaCss(shadowColor, shadowOpacity);
        ctx.strokeText(lineText, centerX, ly);
      }
      ctx.fillText(lineText, centerX, ly);
      ctx.restore();
    }

    // 3. Stroke Outline
    if (strokeWidth > 0) {
      ctx.save();
      ctx.lineWidth = strokeWidth * 2;
      ctx.strokeStyle = strokeColor;
      ctx.strokeText(lineText, centerX, ly);
      ctx.restore();
    }

    // 4. Main Fill Text
    ctx.save();
    ctx.fillStyle = textColor;
    ctx.fillText(lineText, centerX, ly);
    ctx.restore();
  });
}

// Render Full 16:9 Transparent Video + TTS Audio (or No-Voice Silent Subtitle Video)
btnRenderVideo.addEventListener("click", async () => {
  if (!scriptInput.value.trim()) {
    alert("대본을 입력해 주세요.");
    return;
  }

  btnRenderVideo.disabled = true;
  renderProgressWrap.style.display = "flex";
  renderResultCard.classList.remove("visible");
  renderStatusMsg.textContent = toggleNoVoice.checked
    ? "음성 없이 1920x1080 투명 알파 채널 자막 영상 렌더링 중..."
    : "TTS 음성 합성 및 1920x1080 투명 알파 채널 영상 렌더링 중...";

  const payload = {
    script: scriptInput.value,
    spoken_lines: state.lines.map((l) => l.spoken_text),
    no_voice: toggleNoVoice.checked,
    line_duration_sec: parseFloat(lineDurationSlider.value),
    tts_engine: ttsEngineSelect.value,
    typecast_api_key: typecastApiKey.value,
    typecast_actor_id: typecastActorId.value,
    typecast_emotion: typecastEmotion.value,
    edge_voice: edgeVoiceSelect.value,
    speed: parseFloat(ttsSpeed.value),
    pitch: 0,
    line_pause_sec: parseFloat(ttsPause.value),
    exclude_numbers: chkExcludeNumbers.checked,
    exclude_special: chkExcludeSpecial.checked,
    custom_exclude_chars: customExcludeInput.value,
    font_id: fontSelect.value,
    font_size: parseInt(fontSizeSlider.value, 10),
    text_color: textColorPicker.value,
    stroke_color: strokeColorPicker.value,
    stroke_width: parseInt(strokeWidthSlider.value, 10),
    shadow_enabled: chkShadowEnabled.checked,
    shadow_color: shadowColorPicker.value,
    shadow_opacity: parseInt(shadowOpacitySlider.value, 10) / 100.0,
    shadow_offset_x: parseInt(shadowXSlider.value, 10),
    shadow_offset_y: parseInt(shadowYSlider.value, 10),
    shadow_blur: parseInt(shadowBlurSlider.value, 10),
    bg_box_enabled: chkBgboxEnabled.checked,
    bg_box_color: bgboxColorPicker.value,
    bg_box_opacity: parseInt(bgboxOpacitySlider.value, 10) / 100.0,
    y_position_pct: parseFloat(subYSlider.value),
    export_format: exportFormatSelect.value,
  };

  try {
    const res = await fetch("/api/tts/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await parseApiJson(res, "렌더링 중 서버 오류가 발생했습니다. (ffmpeg 설치 여부를 확인해 주세요)");
    if (!res.ok) throw new Error(data.detail || "렌더링 중 오류가 발생했습니다.");

    renderDurationBadge.textContent = `총 ${data.total_duration}초 (${data.used_engine})`;

    // Preview WebM or MOV in player
    const previewUrl = data.webm_url || data.mov_url;
    if (previewUrl) {
      renderedVideoPlayer.src = previewUrl;
      renderedVideoPlayer.style.display = "block";
    } else {
      renderedVideoPlayer.style.display = "none";
    }

    renderDownloadLinks.innerHTML = "";
    if (data.split_zip_url) {
      renderDownloadLinks.innerHTML += `
        <a href="${data.split_zip_url}" download class="btn btn-primary btn-sm">
          줄별 분리 클립 전체 (.ZIP)
        </a>`;
    }
    if (data.mov_url) {
      renderDownloadLinks.innerHTML += `
        <a href="${data.mov_url}" download class="btn btn-sm">
          통합 영상 (.MOV)
        </a>`;
    }
    if (data.webm_url) {
      renderDownloadLinks.innerHTML += `
        <a href="${data.webm_url}" download class="btn btn-sm">
          통합 영상 (.WebM)
        </a>`;
    }
    if (data.audio_url) {
      renderDownloadLinks.innerHTML += `
        <a href="${data.audio_url}" download class="btn btn-sm">
          통합 음성 (.WAV)
        </a>`;
    }
    if (data.srt_url) {
      renderDownloadLinks.innerHTML += `
        <a href="${data.srt_url}" download class="btn btn-sm">
          통합 자막 (.SRT)
        </a>`;
    }

    // Populate Enter-separated per-line clips list
    splitClipsList.innerHTML = "";
    (data.timeline || []).forEach((item) => {
      const clipRow = document.createElement("div");
      clipRow.className = "split-clip-row";

      let btnsHtml = `<div class="split-clip-actions">`;
      if (item.audio_url) {
        btnsHtml += `<a href="${item.audio_url}" download="line_${String(item.index).padStart(2, "0")}.wav" class="btn btn-sm" onclick="event.stopPropagation()">음성 WAV</a>`;
      }
      if (item.mov_url) {
        btnsHtml += `<a href="${item.mov_url}" download="line_${String(item.index).padStart(2, "0")}_alpha.mov" class="btn btn-primary btn-sm" onclick="event.stopPropagation()">투명 MOV</a>`;
      }
      if (item.webm_url) {
        btnsHtml += `<a href="${item.webm_url}" download="line_${String(item.index).padStart(2, "0")}_alpha.webm" class="btn btn-sm" onclick="event.stopPropagation()">투명 WebM</a>`;
      }
      if (item.png_url) {
        btnsHtml += `<a href="${item.png_url}" download="line_${String(item.index).padStart(2, "0")}.png" class="btn btn-sm" onclick="event.stopPropagation()">자막 PNG</a>`;
      }
      btnsHtml += `</div>`;

      clipRow.innerHTML = `
        <div class="split-clip-top">
          <span class="diff-idx">#${item.index}</span>
          <span class="diff-badge">${item.duration}s</span>
          <span class="split-clip-title" title="${escapeHtml(item.display_text)}">${escapeHtml(item.display_text)}</span>
        </div>
        <div class="split-clip-bottom">
          <span class="split-clip-spoken">TTS: ${item.spoken_text ? escapeHtml(item.spoken_text) : "무음 클립"}</span>
          ${btnsHtml}
        </div>
      `;

      clipRow.addEventListener("click", () => {
        const clipPreview = item.webm_url || item.mov_url || item.audio_url;
        if (clipPreview) {
          renderedVideoPlayer.src = clipPreview;
          renderedVideoPlayer.style.display = "block";
          renderedVideoPlayer.play();
        }
      });

      splitClipsList.appendChild(clipRow);
    });

    renderResultCard.classList.add("visible");
  } catch (err) {
    alert(err.message);
  } finally {
    btnRenderVideo.disabled = false;
    renderProgressWrap.style.display = "none";
  }
});

// ============================================================================
// MODE 2: Video Speech Recognition (STT) & Subtitle Extraction
// ============================================================================

let selectedSttFile = null;

sttFileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) handleSttFileSelected(file);
});

sttDropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  sttDropzone.classList.add("dragover");
});

sttDropzone.addEventListener("dragleave", () => {
  sttDropzone.classList.remove("dragover");
});

sttDropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  sttDropzone.classList.remove("dragover");
  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
    handleSttFileSelected(e.dataTransfer.files[0]);
  }
});

function handleSttFileSelected(file) {
  selectedSttFile = file;
  const objUrl = URL.createObjectURL(file);
  sttVideoPreview.src = objUrl;
  sttVideoPreview.style.display = "block";
}

btnRunStt.addEventListener("click", async () => {
  if (!selectedSttFile) {
    alert("음성을 인식할 영상 또는 오디오 파일을 먼저 선택해 주세요.");
    return;
  }

  btnRunStt.disabled = true;
  sttProgressWrap.style.display = "flex";

  const formData = new FormData();
  formData.append("file", selectedSttFile);
  formData.append("language", sttLangSelect.value);
  formData.append("model_size", sttModelSelect.value);
  formData.append("exclude_numbers", sttExcludeNumbers.checked);
  formData.append("exclude_special", sttExcludeSpecial.checked);

  try {
    const res = await fetch("/api/stt/transcribe", {
      method: "POST",
      body: formData,
    });
    const data = await parseApiJson(res, "음성 인식 중 서버 오류가 발생했습니다.");
    if (!res.ok) throw new Error(data.detail || "음성 인식 실패");

    state.sttSegments = data.segments || [];
    state.sttDetectedLang = (data.detected_language || sttLangSelect.value || "ko").toUpperCase();
    updateSttSegmentCountBadge();
    renderSttSegmentsEditor();
    updateSttDownloadLinks(data);

    btnSendToTts.disabled = state.sttSegments.length === 0;
    btnSaveEditedSrt.disabled = state.sttSegments.length === 0;
  } catch (err) {
    alert(err.message);
  } finally {
    btnRunStt.disabled = false;
    sttProgressWrap.style.display = "none";
  }
});

function updateSttSegmentCountBadge() {
  const langSuffix = state.sttDetectedLang ? ` (${state.sttDetectedLang})` : "";
  sttSegmentCount.textContent = `${state.sttSegments.length}개 구간${langSuffix}`;
}

function formatSrtTimestampJs(seconds) {
  const safeSec = Math.max(0, Number(seconds) || 0);
  const ms = Math.round((safeSec % 1) * 1000);
  const totalSec = Math.floor(safeSec) + (ms === 1000 ? 1 : 0);
  const finalMs = ms === 1000 ? 0 : ms;
  const s = totalSec % 60;
  const m = Math.floor(totalSec / 60) % 60;
  const h = Math.floor(totalSec / 3600);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(finalMs).padStart(3, "0")}`;
}

function computeSplitTimingAndWords(seg, beforeText, afterText) {
  const start = Math.max(0, Number(seg.start) || 0);
  const end = Math.max(start, Number(seg.end) || start);
  const totalDur = Math.max(0, end - start);

  const normBefore = beforeText.replace(/\s+/g, "");
  const normAfter = afterText.replace(/\s+/g, "");
  const len1 = normBefore.length || beforeText.length;
  const len2 = normAfter.length || afterText.length;
  const ratio = len1 / Math.max(1, len1 + len2);

  let seg1End = Number((start + totalDur * ratio).toFixed(3));
  let seg2Start = seg1End;
  let seg1Words = [];
  let seg2Words = [];

  if (Array.isArray(seg.words) && seg.words.length >= 2) {
    const wordNorms = seg.words.map((w) => String(w.word || "").replace(/\s+/g, ""));
    const wordsJoined = wordNorms.join("");

    if (wordsJoined.length > 0 && wordsJoined === normBefore + normAfter) {
      let acc = 0;
      for (let k = 0; k < seg.words.length; k++) {
        const wLen = wordNorms[k].length;
        const nextAcc = acc + wLen;
        if (nextAcc === normBefore.length && k < seg.words.length - 1) {
          const w1End = Number(seg.words[k].end);
          const w2Start = Number(seg.words[k + 1].start);
          if (Number.isFinite(w1End) && Number.isFinite(w2Start) && w1End > start && w2Start < end) {
            if (w1End <= w2Start) {
              seg1End = Number(w1End.toFixed(3));
              seg2Start = Number(w2Start.toFixed(3));
            } else {
              const mid = Number(((w1End + w2Start) / 2).toFixed(3));
              seg1End = mid;
              seg2Start = mid;
            }
            seg1Words = seg.words.slice(0, k + 1);
            seg2Words = seg.words.slice(k + 1);
          }
          break;
        } else if (acc < normBefore.length && normBefore.length < nextAcc && wLen > 0) {
          const wStart = Number(seg.words[k].start);
          const wEnd = Number(seg.words[k].end);
          const frac = (normBefore.length - acc) / wLen;
          if (Number.isFinite(wStart) && Number.isFinite(wEnd) && wEnd >= wStart) {
            const splitT = Number((wStart + (wEnd - wStart) * frac).toFixed(3));
            if (splitT > start && splitT < end) {
              seg1End = splitT;
              seg2Start = splitT;
            }
          }
          break;
        }
        acc = nextAcc;
      }
    }
  }

  return { seg1End, seg2Start, seg1Words, seg2Words };
}

let sttAutoExportTimer = null;
function scheduleAutoExportStt() {
  clearTimeout(sttAutoExportTimer);
  sttAutoExportTimer = setTimeout(async () => {
    if (state.sttSegments.length === 0) return;
    try {
      const res = await fetch("/api/stt/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segments: state.sttSegments }),
      });
      if (res.ok) {
        const data = await res.json();
        updateSttDownloadLinks(data);
      }
    } catch (_) {
      // Ignore background auto-export errors
    }
  }, 300);
}

function splitSttSegmentAt(idx, beforeText, afterText) {
  const seg = state.sttSegments[idx];
  if (!seg) return;

  const { seg1End, seg2Start, seg1Words, seg2Words } = computeSplitTimingAndWords(seg, beforeText, afterText);
  const start = Math.max(0, Number(seg.start) || 0);
  const end = Math.max(seg2Start, Number(seg.end) || seg2Start);

  const seg1 = {
    ...seg,
    start,
    end: seg1End,
    start_srt: formatSrtTimestampJs(start),
    end_srt: formatSrtTimestampJs(seg1End),
    text: beforeText,
    words: seg1Words,
  };

  const seg2 = {
    ...seg,
    start: seg2Start,
    end,
    start_srt: formatSrtTimestampJs(seg2Start),
    end_srt: formatSrtTimestampJs(end),
    text: afterText,
    words: seg2Words,
  };

  state.sttSegments.splice(idx, 1, seg1, seg2);
  state.sttSegments.forEach((s, i) => {
    s.index = i + 1;
  });

  updateSttSegmentCountBadge();
  renderSttSegmentsEditor(idx + 1, 0);
  scheduleAutoExportStt();
}

function updateSttDownloadLinks(data) {
  sttDownloadLinks.innerHTML = "";
  if (data.srt_url) {
    sttDownloadLinks.innerHTML += `<a href="${data.srt_url}" download class="btn btn-primary btn-sm">SRT 자막 다운로드 (.srt)</a>`;
  }
  if (data.vtt_url) {
    sttDownloadLinks.innerHTML += `<a href="${data.vtt_url}" download class="btn btn-sm">WebVTT 자막 다운로드 (.vtt)</a>`;
  }
  if (data.txt_url) {
    sttDownloadLinks.innerHTML += `<a href="${data.txt_url}" download class="btn btn-sm">대본 텍스트 다운로드 (.txt)</a>`;
  }
}

function renderSttSegmentsEditor(focusIdx = null, caretPos = 0) {
  sttSegmentsList.innerHTML = "";
  if (state.sttSegments.length === 0) {
    sttSegmentsList.innerHTML = `<div style="padding: 36px; text-align: center; color: var(--text-muted);">인식된 음성이 없습니다.</div>`;
    return;
  }

  state.sttSegments.forEach((seg, idx) => {
    const row = document.createElement("div");
    row.className = "stt-seg-item";
    row.innerHTML = `
      <div class="diff-idx">#${idx + 1}</div>
      <div class="stt-time-pair">
        <input type="number" step="0.1" value="${seg.start}" data-idx="${idx}" data-field="start" aria-label="시작 시간(초)" />
        <span>→</span>
        <input type="number" step="0.1" value="${seg.end}" data-idx="${idx}" data-field="end" aria-label="종료 시간(초)" />
      </div>
      <input type="text" class="stt-text-input" value="${escapeHtml(seg.text)}" data-idx="${idx}" data-field="text" placeholder="Enter를 누르면 커서 위치에서 자막이 분리됩니다" aria-label="자막 텍스트" />
      <button type="button" class="btn btn-sm" data-seek="${seg.start}">재생</button>
    `;

    row.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        const f = e.target.dataset.field;
        if (f === "text") {
          state.sttSegments[i].text = e.target.value;
        } else {
          const numVal = parseFloat(e.target.value) || 0;
          state.sttSegments[i][f] = numVal;
          state.sttSegments[i][`${f}_srt`] = formatSrtTimestampJs(numVal);
        }
        scheduleAutoExportStt();
      });
    });

    const textInput = row.querySelector(".stt-text-input");
    if (textInput) {
      textInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.isComposing) {
          e.preventDefault();
          const fullText = textInput.value;
          const selStart = textInput.selectionStart ?? fullText.length;
          const selEnd = textInput.selectionEnd ?? selStart;
          const beforeText = fullText.slice(0, selStart).trim();
          const afterText = fullText.slice(selEnd).trim();
          if (!beforeText || !afterText) {
            return;
          }
          splitSttSegmentAt(idx, beforeText, afterText);
        }
      });
    }

    const seekBtn = row.querySelector("[data-seek]");
    seekBtn.addEventListener("click", () => {
      sttVideoPreview.currentTime = parseFloat(state.sttSegments[idx]?.start) || 0;
      sttVideoPreview.play();
    });

    sttSegmentsList.appendChild(row);
  });

  if (focusIdx !== null) {
    const targetInput = sttSegmentsList.querySelector(`.stt-text-input[data-idx="${focusIdx}"]`);
    if (targetInput) {
      targetInput.focus();
      try {
        targetInput.setSelectionRange(caretPos, caretPos);
      } catch (_) {}
    }
  }
}

btnSaveEditedSrt.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/stt/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments: state.sttSegments }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error("자막 내보내기 실패");
    updateSttDownloadLinks(data);
  } catch (err) {
    alert(err.message);
  }
});

btnSendToTts.addEventListener("click", () => {
  if (state.sttSegments.length === 0) return;
  scriptInput.value = state.sttSegments.map((s) => s.text.trim()).filter(Boolean).join("\n");
  document.getElementById("tab-btn-tts").click();
  updateScriptLinesPreview();
});

// Initialize on page load
(async function init() {
  syncNoVoiceUI();
  await loadFontsList();
  await updateScriptLinesPreview();
})();
