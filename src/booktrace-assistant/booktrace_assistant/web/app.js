const TOKEN = window.BOOKTRACE_TOKEN;
const headers = { "Content-Type": "application/json", "X-BookTrace-Token": TOKEN };

const chat = document.querySelector("#chat");
const welcome = document.querySelector("#welcome");
const messages = document.querySelector("#messages");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const attachButton = document.querySelector("#attach-button");
const fileInput = document.querySelector("#file-input");
const attachmentsEl = document.querySelector("#attachment-list");
const dropZone = document.querySelector("#drop-zone");
const statusBar = document.querySelector("#status-bar");
const statusText = document.querySelector("#status-text");
const cancelButton = document.querySelector("#cancel-job");
const settingsDialog = document.querySelector("#settings-dialog");
const confirmDialog = document.querySelector("#confirm-dialog");
const engineSelect = document.querySelector("#engine-select");
const modelSelect = document.querySelector("#model-select");
const customModelWrap = document.querySelector("#custom-model-wrap");
const customModel = document.querySelector("#custom-model");
const autoRetry = document.querySelector("#auto-retry");
const effortSelect = document.querySelector("#effort-select");
const statusElapsed = document.querySelector("#status-elapsed");
const showProgressButton = document.querySelector("#show-progress");
const modelBadge = document.querySelector("#model-badge");
const toast = document.querySelector("#toast");

let pendingFiles = [];
let coverIndex = -1;
let lastEventId = 0;
let busy = false;
let busyMode = "";
let retryDeadline = null;
let settings = null;
let currentCard = null;
let currentSaveButton = null;
let stopped = false;
let progress = null;

const STEP_ICONS = { note: "💬", think: "🧠", search: "🔍", fetch: "🌐", booktrace: "📚", image: "🖼️", error: "⚠️" };

function escapeText(value) {
  return String(value ?? "");
}

function showToast(message, duration = 3600) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), duration);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });
  let payload = {};
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(payload.error || `操作失敗（${response.status}）`);
  return payload;
}

function scrollToBottom() {
  requestAnimationFrame(() => chat.scrollTo({ top: chat.scrollHeight, behavior: "smooth" }));
}

function setBusy(value, mode = "", label = "") {
  const changed = busy !== value || busyMode !== mode;
  busy = value;
  busyMode = mode;
  sendButton.disabled = value;
  attachButton.disabled = value;
  input.disabled = value;
  if (value) {
    statusBar.classList.remove("hidden");
    statusText.textContent = label || "正在處理…";
    cancelButton.classList.toggle("hidden", mode === "save");
    showProgressButton.classList.toggle("hidden", !(progress && progress.running));
  } else {
    statusBar.classList.add("hidden");
    statusElapsed.textContent = "";
    retryDeadline = null;
    input.disabled = false;
    if (changed && !settingsDialog.open && !confirmDialog.open) input.focus();
  }
}

function addMessage(role, text, imageUrls = []) {
  welcome.classList.add("hidden");
  const row = document.createElement("div");
  row.className = `message ${role}`;
  if (role === "assistant") {
    const avatar = document.createElement("div");
    avatar.className = "assistant-avatar";
    avatar.textContent = "B";
    row.appendChild(avatar);
  }
  const content = document.createElement("div");
  content.className = "message-content";
  if (imageUrls.length) {
    const gallery = document.createElement("div");
    gallery.className = "message-images";
    imageUrls.forEach((url) => {
      const image = document.createElement("img");
      image.src = url;
      image.alt = "書本照片";
      gallery.appendChild(image);
    });
    content.appendChild(gallery);
  }
  if (text) {
    const body = document.createElement("div");
    body.className = "message-text";
    body.textContent = text;
    content.appendChild(body);
  }
  row.appendChild(content);
  messages.appendChild(row);
  scrollToBottom();
  return content;
}

function fact(label, value) {
  if (!value) return [];
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  return [dt, dd];
}

function renderOutcome(outcome, attempts) {
  const content = addMessage("assistant", outcome.summary || "查證完成。", []);
  const card = document.createElement("section");
  card.className = "book-card";
  currentCard = card;
  currentSaveButton = null;

  const main = document.createElement("div");
  main.className = "book-card-main";
  const cover = document.createElement("div");
  cover.className = "cover-shell";
  cover.dataset.role = "cover";
  cover.textContent = outcome.ready ? "正在準備封面…" : "尚未確認封面";
  main.appendChild(cover);

  const info = document.createElement("div");
  const badge = document.createElement("span");
  badge.className = `book-status ${outcome.ready ? "" : "needs"}`;
  badge.textContent = outcome.ready ? "版本已核對" : outcome.status === "needs_clarification" ? "需要補充" : "尚未確認";
  info.appendChild(badge);
  if (outcome.book.title) {
    const title = document.createElement("h2");
    title.className = "book-title";
    title.textContent = outcome.book.title;
    info.appendChild(title);
  }
  if (outcome.book.author) {
    const byline = document.createElement("div");
    byline.className = "book-byline";
    byline.textContent = outcome.book.author;
    info.appendChild(byline);
  }
  const facts = document.createElement("dl");
  facts.className = "book-facts";
  [
    fact("ISBN", outcome.book.isbn),
    fact("出版社", outcome.book.publisher),
    fact("出版日期", outcome.book.publicationDate),
    fact("分類", outcome.book.category),
    fact("書架狀態", outcome.book.existingBookId ? `已有藏書 #${outcome.book.existingBookId}` : "尚未找到同版本"),
  ].flat().forEach((node) => facts.appendChild(node));
  info.appendChild(facts);
  main.appendChild(info);
  card.appendChild(main);

  const extra = document.createElement("div");
  extra.className = "book-card-extra";
  if (outcome.candidates?.length) {
    const box = document.createElement("div");
    box.className = "candidates";
    const strong = document.createElement("strong");
    strong.textContent = "可能的版本";
    box.appendChild(strong);
    const list = document.createElement("ol");
    outcome.candidates.forEach((candidate) => {
      const li = document.createElement("li");
      li.textContent = [candidate.title, candidate.isbn, candidate.publication_year, candidate.pages, candidate.binding, candidate.cover_description].filter(Boolean).join(" · ");
      list.appendChild(li);
    });
    box.appendChild(list);
    extra.appendChild(box);
  }
  if (outcome.questions?.length) {
    const box = document.createElement("div");
    box.className = "questions";
    const strong = document.createElement("strong");
    strong.textContent = "請直接在下方回覆";
    box.appendChild(strong);
    const list = document.createElement("ul");
    outcome.questions.forEach((question) => {
      const li = document.createElement("li");
      li.textContent = question;
      list.appendChild(li);
    });
    box.appendChild(list);
    extra.appendChild(box);
  }
  if (outcome.book.sources?.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `查看 ${outcome.book.sources.length} 個核對來源`;
    details.appendChild(summary);
    outcome.book.sources.forEach((url) => {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noreferrer noopener";
      link.textContent = url;
      details.appendChild(link);
    });
    extra.appendChild(details);
  }
  card.appendChild(extra);

  if (outcome.ready) {
    const saveRow = document.createElement("div");
    saveRow.className = "save-row";
    const hint = document.createElement("small");
    hint.textContent = "看過封面後，再決定要不要加入書架。";
    const button = document.createElement("button");
    button.className = "save-book-button";
    button.type = "button";
    button.disabled = true;
    button.textContent = "加入 BookTrace";
    button.addEventListener("click", () => {
      document.querySelector("#confirm-text").textContent = `確認要把《${outcome.book.title || "這本書"}》加入或補齊 BookTrace 嗎？`;
      confirmDialog.showModal();
    });
    currentSaveButton = button;
    saveRow.append(hint, button);
    card.appendChild(saveRow);
  }
  content.appendChild(card);
  if (attempts > 1) {
    const retryNote = document.createElement("small");
    retryNote.style.color = "var(--muted)";
    retryNote.textContent = `自動重試 ${attempts - 1} 次後完成`;
    content.appendChild(retryNote);
  }
  scrollToBottom();
}

function setCover(url) {
  if (!currentCard) return;
  const shell = currentCard.querySelector('[data-role="cover"]');
  if (!shell) return;
  shell.textContent = "";
  const image = document.createElement("img");
  image.src = url;
  image.alt = "已核對的書籍封面";
  image.addEventListener("click", () => window.open(url, "_blank", "noopener"));
  shell.appendChild(image);
  if (currentSaveButton) currentSaveButton.disabled = false;
}

function addError(message) {
  const content = addMessage("assistant", "", []);
  const error = document.createElement("div");
  error.className = "assistant-error";
  error.textContent = message;
  content.appendChild(error);
}

function addSaved(event) {
  const content = addMessage("assistant", "", []);
  const card = document.createElement("div");
  card.className = "saved-card";
  const title = document.createElement("strong");
  title.textContent = `已${event.created ? "加入" : "補齊"}《${event.title || "這本書"}》`;
  const detail = document.createElement("div");
  detail.textContent = `BookTrace ID：${event.bookId ?? "—"} · 封面已讀回驗證`;
  const link = document.createElement("a");
  link.href = event.site;
  link.target = "_blank";
  link.rel = "noreferrer noopener";
  link.textContent = "開啟 BookTrace →";
  card.append(title, detail, link);
  content.appendChild(card);
  if (currentSaveButton) {
    currentSaveButton.disabled = true;
    currentSaveButton.textContent = "已加入";
  }
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} 分 ${seconds % 60} 秒` : `${seconds} 秒`;
}

function updateProgressSummary() {
  if (!progress) return;
  const steps = `${progress.count} 步`;
  if (progress.running) {
    progress.summary.textContent = `查證過程 · 進行中（${steps}）`;
  } else {
    progress.summary.textContent = ["查證過程", steps, progress.finishedText].filter(Boolean).join(" · ");
  }
}

function startProgress(event) {
  const content = addMessage("assistant", "", []);
  const details = document.createElement("details");
  details.className = "progress-log";
  const summary = document.createElement("summary");
  const meta = document.createElement("div");
  meta.className = "progress-meta";
  meta.textContent = `${event.engine} · ${event.model} · 思考：${event.effort}`;
  const list = document.createElement("ol");
  list.className = "progress-steps";
  details.append(summary, meta, list);
  content.appendChild(details);
  progress = { details, summary, list, count: 0, running: true, startedAt: event.at || Date.now() / 1000, finishedText: "" };
  const waiting = document.createElement("li");
  waiting.className = "progress-step step-waiting";
  waiting.textContent = "已送出，等待 AI 開始（閱讀技能說明、思考中）…";
  list.appendChild(waiting);
  progress.waiting = waiting;
  updateProgressSummary();
  showProgressButton.classList.remove("hidden");
}

function addStep(event) {
  if (!progress) return;
  if (progress.waiting) {
    progress.waiting.remove();
    progress.waiting = null;
  }
  const item = document.createElement("li");
  item.className = `progress-step step-${event.kind}`;
  const icon = document.createElement("span");
  icon.className = "step-icon";
  icon.textContent = STEP_ICONS[event.kind] || "•";
  const body = document.createElement("span");
  body.className = "step-text";
  const text = event.text || "";
  const splitAt = text.indexOf("：");
  const url = splitAt >= 0 ? text.slice(splitAt + 1).trim() : "";
  if (event.kind === "fetch" && /^https?:\/\//.test(url)) {
    body.append(text.slice(0, splitAt + 1));
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    link.textContent = url;
    body.appendChild(link);
  } else {
    body.textContent = text;
  }
  item.append(icon, body);
  progress.list.appendChild(item);
  progress.count += 1;
  updateProgressSummary();
  if (progress.details.open) {
    const nearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 160;
    if (nearBottom) scrollToBottom();
  }
}

function finishProgress(event) {
  if (!progress) return;
  progress.running = false;
  if (progress.waiting) {
    progress.waiting.remove();
    progress.waiting = null;
  }
  const parts = [formatDuration(event.seconds || 0)];
  if (event.usage) parts.push(event.usage);
  if ((event.attempts || 1) > 1) parts.push(`重試 ${event.attempts - 1} 次`);
  if (!event.ok) parts.push("未完成");
  progress.finishedText = parts.join(" · ");
  updateProgressSummary();
  showProgressButton.classList.add("hidden");
}

function processEvent(event) {
  lastEventId = Math.max(lastEventId, event.id || 0);
  switch (event.type) {
    case "run_started":
      startProgress(event);
      break;
    case "step":
      addStep(event);
      break;
    case "run_finished":
      finishProgress(event);
      break;
    case "reset":
      progress = null;
      messages.textContent = "";
      welcome.classList.remove("hidden");
      currentCard = null;
      currentSaveButton = null;
      break;
    case "user":
      addMessage("user", event.text, event.images || []);
      currentCard = null;
      currentSaveButton = null;
      break;
    case "assistant":
      renderOutcome(event.outcome, event.attempts || 1);
      break;
    case "assistant_error":
      addError(event.message || "處理未完成。請再試一次。");
      break;
    case "cover_ready":
      setCover(event.url);
      break;
    case "cover_error":
      addError(event.message || "封面尚未準備完成。");
      break;
    case "saved":
      addSaved(event);
      break;
    case "busy":
      setBusy(event.busy, event.mode, event.status);
      break;
    case "status":
      if (busy) statusText.textContent = event.message;
      break;
    case "retry":
      retryDeadline = event.deadline || null;
      statusBar.classList.remove("hidden");
      break;
    case "settings":
      settings = event.settings;
      renderSettings();
      break;
  }
}

async function pollEvents() {
  if (stopped) return;
  try {
    const data = await api(`/api/events?after=${lastEventId}`, { method: "GET", headers: { "X-BookTrace-Token": TOKEN } });
    (data.events || []).forEach(processEvent);
    if (data.state) setBusy(data.state.busy, data.state.busyMode, data.state.status);
  } catch (error) {
    if (!stopped) showToast(error.message);
  } finally {
    if (!stopped) setTimeout(pollEvents, busy ? 650 : 1100);
  }
}

function updateCountdown() {
  if (busy && progress && progress.running) {
    statusElapsed.textContent = `已進行 ${formatDuration(Date.now() / 1000 - progress.startedAt)}`;
  }
  if (!retryDeadline || !busy) return;
  const remaining = Math.max(0, Math.floor(retryDeadline - Date.now() / 1000));
  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const seconds = remaining % 60;
  const clock = hours ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}` : `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  statusText.textContent = `等待額度或服務恢復，${clock} 後自動重試`;
}
setInterval(updateCountdown, 500);

function autoGrow() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

function addFiles(files) {
  const allowed = ["image/jpeg", "image/png", "image/gif", "image/webp"];
  for (const file of files) {
    if (pendingFiles.length >= 4) { showToast("一次最多加入 4 張圖片"); break; }
    if (!allowed.includes(file.type)) { showToast(`${file.name || "這張圖片"} 不是支援的 JPG、PNG、GIF 或 WebP`); continue; }
    if (file.size > 5 * 1024 * 1024) { showToast(`${file.name || "這張圖片"} 超過 5 MB`); continue; }
    pendingFiles.push({ file, url: URL.createObjectURL(file) });
  }
  renderAttachments();
}

function renderAttachments() {
  attachmentsEl.textContent = "";
  pendingFiles.forEach((item, index) => {
    const card = document.createElement("div");
    card.className = `attachment ${coverIndex === index ? "is-cover" : ""}`;
    const image = document.createElement("img");
    image.src = item.url;
    image.alt = item.file.name || `圖片 ${index + 1}`;
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "移除圖片");
    remove.addEventListener("click", () => {
      URL.revokeObjectURL(item.url);
      pendingFiles.splice(index, 1);
      if (coverIndex === index) coverIndex = -1;
      else if (coverIndex > index) coverIndex -= 1;
      renderAttachments();
    });
    const choose = document.createElement("button");
    choose.className = "cover-choice";
    choose.type = "button";
    choose.textContent = coverIndex === index ? "✓ 這張是封面" : "這張是封面";
    choose.addEventListener("click", () => { coverIndex = coverIndex === index ? -1 : index; renderAttachments(); });
    card.append(image, remove, choose);
    attachmentsEl.appendChild(card);
  });
}

async function fileToBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

async function sendMessage() {
  const text = input.value.trim();
  if (busy || (!text && !pendingFiles.length)) return;
  sendButton.disabled = true;
  statusBar.classList.remove("hidden");
  statusText.textContent = "正在送出…";
  try {
    const images = [];
    for (const item of pendingFiles) {
      images.push({ name: item.file.name, type: item.file.type, data: await fileToBase64(item.file) });
    }
    await api("/api/message", { method: "POST", body: JSON.stringify({ text, images, coverIndex }) });
    pendingFiles.forEach((item) => URL.revokeObjectURL(item.url));
    pendingFiles = [];
    coverIndex = -1;
    renderAttachments();
    input.value = "";
    autoGrow();
  } catch (error) {
    showToast(error.message);
    statusBar.classList.add("hidden");
    sendButton.disabled = false;
  }
}

input.addEventListener("input", autoGrow);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendMessage();
  }
});
input.addEventListener("paste", (event) => {
  const files = [...(event.clipboardData?.items || [])]
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  if (files.length) {
    event.preventDefault();
    addFiles(files);
  }
});
sendButton.addEventListener("click", sendMessage);
attachButton.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { addFiles([...fileInput.files]); fileInput.value = ""; });

["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => addFiles([...event.dataTransfer.files]));

document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
  input.value = button.dataset.prompt;
  autoGrow();
  input.focus();
}));

showProgressButton.addEventListener("click", () => {
  if (!progress) return;
  progress.details.open = true;
  progress.details.scrollIntoView({ behavior: "smooth", block: "start" });
});

cancelButton.addEventListener("click", async () => {
  try { await api("/api/cancel", { method: "POST", body: "{}" }); }
  catch (error) { showToast(error.message); }
});

document.querySelector("#new-chat").addEventListener("click", async () => {
  if (busy) { showToast("請先按「停止」，等目前處理結束後再開始新對話"); return; }
  if (messages.children.length && !confirm("要開始找另一本書嗎？目前對話會清空。")) return;
  try { await api("/api/new", { method: "POST", body: "{}" }); }
  catch (error) { showToast(error.message); }
});

function modelLabel(engine, model) {
  const option = settings?.modelOptions?.[engine]?.find((item) => item.value === model);
  return option?.label || model || "CLI 預設";
}

function effortLabel(effort) {
  const option = settings?.effortOptions?.find((item) => item.value === effort);
  return (option?.label || effort || "自動").split("·")[0].replace(/（.*）/, "").trim();
}

function renderSettings() {
  if (!settings) return;
  engineSelect.textContent = "";
  settings.engines.forEach((engine) => {
    const option = document.createElement("option");
    option.value = engine.value;
    option.textContent = engine.label;
    engineSelect.appendChild(option);
  });
  engineSelect.value = settings.engine;
  fillModelOptions(settings.engine, settings.models[settings.engine] || "");
  autoRetry.checked = settings.autoRetry;
  effortSelect.textContent = "";
  (settings.effortOptions || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    effortSelect.appendChild(option);
  });
  effortSelect.value = settings.effort || "";
  const engineName = settings.engine === "codex" ? "Codex" : "Claude";
  const model = modelLabel(settings.engine, settings.models[settings.engine] || "").split("·")[0].trim();
  modelBadge.textContent = `${engineName} · ${model} · 思考：${effortLabel(settings.effort || "")}`;
}

function fillModelOptions(engine, selected) {
  modelSelect.textContent = "";
  const options = settings.modelOptions[engine] || [];
  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    modelSelect.appendChild(option);
  });
  const known = options.some((item) => item.value === selected);
  const custom = document.createElement("option");
  custom.value = "__custom__";
  custom.textContent = "自訂模型 ID…";
  modelSelect.appendChild(custom);
  modelSelect.value = known ? selected : "__custom__";
  customModel.value = known ? "" : selected;
  customModelWrap.classList.toggle("hidden", modelSelect.value !== "__custom__");
}

engineSelect.addEventListener("change", () => fillModelOptions(engineSelect.value, settings.models[engineSelect.value] || ""));
modelSelect.addEventListener("change", () => customModelWrap.classList.toggle("hidden", modelSelect.value !== "__custom__"));
document.querySelector("#open-settings").addEventListener("click", () => { renderSettings(); settingsDialog.showModal(); });
modelBadge.addEventListener("click", () => { renderSettings(); settingsDialog.showModal(); });

document.querySelector("#save-settings").addEventListener("click", async (event) => {
  event.preventDefault();
  const model = modelSelect.value === "__custom__" ? customModel.value.trim() : modelSelect.value;
  try {
    const data = await api("/api/settings", { method: "POST", body: JSON.stringify({ engine: engineSelect.value, model, effort: effortSelect.value, autoRetry: autoRetry.checked }) });
    settings = data.settings;
    renderSettings();
    settingsDialog.close();
    showToast("設定已儲存", 1800);
  } catch (error) { showToast(error.message); }
});

document.querySelector("#confirm-save").addEventListener("click", async (event) => {
  event.preventDefault();
  confirmDialog.close();
  try { await api("/api/save", { method: "POST", body: JSON.stringify({ confirmed: true }) }); }
  catch (error) { showToast(error.message); }
});

document.querySelector("#shutdown-app").addEventListener("click", async () => {
  if (busy) { showToast("請先等目前工作完成或按停止"); return; }
  if (!confirm("要結束 BookTrace 小幫手嗎？")) return;
  try {
    await api("/api/shutdown", { method: "POST", body: "{}" });
    stopped = true;
    document.body.innerHTML = '<main class="welcome"><div class="welcome-icon">B</div><h1>BookTrace 小幫手已結束</h1><p>可以關閉這個分頁。</p></main>';
  } catch (error) { showToast(error.message); }
});

async function initialize() {
  try {
    const state = await api("/api/state", { method: "GET", headers: { "X-BookTrace-Token": TOKEN } });
    settings = state.settings;
    renderSettings();
    setBusy(state.busy, state.busyMode, state.status);
    pollEvents();
    input.focus();
  } catch (error) {
    addError(`無法連接本機 BookTrace 小幫手：${error.message}`);
  }
}

initialize();
