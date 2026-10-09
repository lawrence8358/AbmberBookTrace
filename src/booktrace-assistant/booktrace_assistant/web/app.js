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
const itemsUI = {};
let pendingSave = null;
let batchRows = [];
let stopped = false;
const progresses = {};

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

function isResearching() {
  return busy && busyMode === "research";
}

function runningProgresses() {
  return Object.values(progresses).filter((entry) => entry.running);
}

function setBusy(value, mode = "", label = "") {
  const changed = busy !== value || busyMode !== mode;
  busy = value;
  busyMode = mode;
  // Only research locks the box; books being saved must not stop you from searching on.
  const researching = isResearching();
  sendButton.disabled = researching;
  attachButton.disabled = researching;
  input.disabled = researching;
  if (value) {
    statusBar.classList.remove("hidden");
    statusText.textContent = label || "正在處理…";
    cancelButton.classList.toggle("hidden", mode === "save");
    showProgressButton.classList.toggle("hidden", !runningProgresses().length);
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

function itemUI(itemId) {
  return (itemsUI[itemId] ||= { label: "", title: "", card: null, saveButton: null, saved: false, saving: false });
}

function itemName(itemId) {
  const ui = itemsUI[itemId];
  return ui ? ui.title || ui.label : "";
}

function renderOutcome(outcome, attempts, itemId) {
  const content = addMessage("assistant", outcome.summary || "查證完成。", []);
  const card = document.createElement("section");
  card.className = "book-card";
  const ui = itemUI(itemId);
  ui.card = card;
  ui.saveButton = null;
  ui.title = outcome.book.title || ui.title;

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
    list.className = "candidate-list";
    outcome.candidates.forEach((candidate) => {
      const li = document.createElement("li");
      li.className = "candidate";
      if (candidate.cover_media) {
        const thumb = document.createElement("img");
        thumb.src = candidate.cover_media;
        thumb.alt = "候選版本封面";
        thumb.addEventListener("click", () => window.open(candidate.cover_media, "_blank", "noopener"));
        li.appendChild(thumb);
      }
      const body = document.createElement("div");
      body.className = "candidate-body";
      body.textContent = [candidate.title, candidate.isbn, candidate.publication_year, candidate.pages, candidate.binding, candidate.cover_description].filter(Boolean).join(" · ");
      li.appendChild(body);
      if (candidate.isbn || candidate.title) {
        const pick = document.createElement("button");
        pick.type = "button";
        pick.className = "secondary candidate-pick";
        pick.textContent = "就是這本";
        pick.addEventListener("click", async () => {
          const text = `請以這個版本為準：${[candidate.title, candidate.isbn && `ISBN ${candidate.isbn}`, candidate.publication_year && `${candidate.publication_year} 年版`].filter(Boolean).join("，")}`;
          try {
            await api("/api/message", { method: "POST", body: JSON.stringify({ text, contextItemId: itemId }) });
            pick.disabled = true;
            pick.textContent = "已選這本";
          } catch (error) { showToast(error.message); }
        });
        li.appendChild(pick);
      }
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
      pendingSave = { itemId };
      confirmDialog.showModal();
    });
    ui.saveButton = button;
    saveRow.append(hint, button);
    card.appendChild(saveRow);
  } else {
    const refine = document.createElement("div");
    refine.className = "refine-row";
    const field = document.createElement("input");
    field.type = "text";
    field.placeholder = "補充線索（例如 ISBN、出版年、封面特徵）後重新查證";
    const go = document.createElement("button");
    go.type = "button";
    go.className = "secondary";
    go.textContent = "補充後重查";
    const submit = async () => {
      const text = field.value.trim();
      if (!text) { field.focus(); return; }
      try { await api("/api/message", { method: "POST", body: JSON.stringify({ text, contextItemId: itemId }) }); }
      catch (error) { showToast(error.message); }
    };
    go.addEventListener("click", submit);
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.isComposing) { event.preventDefault(); submit(); }
    });
    refine.append(field, go);
    card.appendChild(refine);
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

function setCover(url, itemId) {
  const ui = itemsUI[itemId];
  if (!ui || !ui.card) return;
  const shell = ui.card.querySelector('[data-role="cover"]');
  if (!shell) return;
  shell.textContent = "";
  const image = document.createElement("img");
  image.src = url;
  image.alt = "已核對的書籍封面";
  image.addEventListener("click", () => window.open(url, "_blank", "noopener"));
  shell.appendChild(image);
  if (ui.saveButton) ui.saveButton.disabled = false;
}

function addError(message, itemId = "") {
  const name = itemName(itemId);
  if (name && Object.keys(itemsUI).length > 1) message = `《${name}》：${message}`;
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
  const ui = itemsUI[event.itemId];
  if (ui?.saveButton) {
    ui.saveButton.disabled = true;
    ui.saveButton.textContent = "已加入";
    ui.saved = true;
    ui.saving = false;
  }
}

// A save that did not go through (or was refused) puts the card's button back so it can be tried again.
function restoreSaveButton(itemId) {
  const ui = itemsUI[itemId];
  if (!ui?.saveButton || ui.saved || !ui.saving) return;
  ui.saving = false;
  ui.saveButton.disabled = false;
  ui.saveButton.textContent = "加入 BookTrace";
}

function addBatchSummary(event) {
  const content = addMessage("assistant", "", []);
  const box = document.createElement("div");
  box.className = "batch-summary";
  const text = document.createElement("div");
  const unsaved = (event.itemIds || []).filter((id) => itemsUI[id]?.saveButton && !itemsUI[id].saved && !itemsUI[id].saving).length;
  text.textContent = `已查完 ${event.total} 本，其中 ${event.ready} 本版本與封面都核對好了。` +
    (event.ready < event.total ? "其他的請看各自卡片上的說明。" : "");
  box.appendChild(text);
  if (unsaved) {
    const all = document.createElement("button");
    all.type = "button";
    all.className = "save-book-button";
    all.textContent = `全部加入（${unsaved} 本）`;
    all.addEventListener("click", () => {
      pendingSave = { all: true };
      document.querySelector("#confirm-text").textContent = `確認要把這 ${unsaved} 本書都加入或補齊 BookTrace 嗎？（只會寫入封面已確認的書）`;
      confirmDialog.showModal();
    });
    box.appendChild(all);
  }
  content.appendChild(box);
  scrollToBottom();
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} 分 ${seconds % 60} 秒` : `${seconds} 秒`;
}

function updateProgressSummary(progress) {
  const steps = `${progress.count} 步`;
  // With several books researched at once, each log says whose it is.
  const whose = Object.keys(itemsUI).length > 1 ? itemName(progress.itemId) : "";
  const title = whose ? `《${whose}》查證過程` : "查證過程";
  if (progress.running) {
    progress.summary.textContent = `${title} · 進行中（${steps}）`;
  } else {
    progress.summary.textContent = [title, steps, progress.finishedText].filter(Boolean).join(" · ");
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
  const progress = { itemId: event.itemId, details, summary, list, count: 0, running: true, startedAt: event.at || Date.now() / 1000, finishedText: "" };
  progresses[event.itemId] = progress;
  const waiting = document.createElement("li");
  waiting.className = "progress-step step-waiting";
  waiting.textContent = "已送出，等待 AI 開始（閱讀技能說明、思考中）…";
  list.appendChild(waiting);
  progress.waiting = waiting;
  updateProgressSummary(progress);
  showProgressButton.classList.remove("hidden");
}

function addStep(event) {
  const progress = progresses[event.itemId];
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
  updateProgressSummary(progress);
  if (progress.details.open) {
    const nearBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 160;
    if (nearBottom) scrollToBottom();
  }
}

function finishProgress(event) {
  const progress = progresses[event.itemId];
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
  updateProgressSummary(progress);
  if (!runningProgresses().length) showProgressButton.classList.add("hidden");
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
      Object.keys(progresses).forEach((id) => delete progresses[id]);
      messages.textContent = "";
      welcome.classList.remove("hidden");
      Object.keys(itemsUI).forEach((id) => delete itemsUI[id]);
      break;
    case "user": {
      const ui = itemUI(event.itemId);
      ui.label = (event.text || "").split("\n")[0].slice(0, 30) || "照片中的書";
      const content = addMessage("user", event.text, event.images || []);
      if (event.total > 1) {
        const tag = document.createElement("span");
        tag.className = "item-label";
        tag.textContent = `第 ${event.index} / ${event.total} 本`;
        content.prepend(tag);
      }
      break;
    }
    case "assistant":
      renderOutcome(event.outcome, event.attempts || 1, event.itemId);
      break;
    case "assistant_error":
      addError(event.message || "處理未完成。請再試一次。", event.itemId);
      restoreSaveButton(event.itemId);
      break;
    case "cover_ready":
      setCover(event.url, event.itemId);
      break;
    case "cover_error":
      addError(event.message || "封面尚未準備完成。", event.itemId);
      break;
    case "saved":
      addSaved(event);
      break;
    case "batch_finished":
      addBatchSummary(event);
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
  const running = runningProgresses();
  if (busy && running.length) {
    const startedAt = Math.min(...running.map((entry) => entry.startedAt));
    statusElapsed.textContent = `已進行 ${formatDuration(Date.now() / 1000 - startedAt)}`;
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
  if (isResearching() || (!text && !pendingFiles.length)) return;
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
  const progress = runningProgresses()[0];
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
  const engineName = settings.engines.find((item) => item.value === settings.engine)?.label || settings.engine;
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
  const target = pendingSave || {};
  pendingSave = null;
  const ui = target.itemId ? itemsUI[target.itemId] : null;
  if (ui?.saveButton) {
    // Saving runs beside the research that may still be going on, so show it started right away.
    ui.saving = true;
    ui.saveButton.disabled = true;
    ui.saveButton.textContent = "加入中…";
  }
  try {
    await api("/api/save", { method: "POST", body: JSON.stringify({ confirmed: true, itemId: target.itemId || "", all: !!target.all }) });
    if (target.all) {
      // Every card whose cover is confirmed (button enabled) is now queued to be saved.
      Object.values(itemsUI).forEach((entry) => {
        if (entry.saveButton && !entry.saved && !entry.saving && !entry.saveButton.disabled) {
          entry.saving = true;
          entry.saveButton.disabled = true;
          entry.saveButton.textContent = "加入中…";
        }
      });
      showToast("已開始加入，過程中可以繼續查書", 2600);
    }
  } catch (error) {
    showToast(error.message);
    if (target.itemId) restoreSaveButton(target.itemId);
  }
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

// ---- 一次查多本書 ----
const batchDialog = document.querySelector("#batch-dialog");
const batchRowsEl = document.querySelector("#batch-rows");
const batchPhotoInput = document.querySelector("#batch-photo-input");
const MAX_BATCH = 10;
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];

function newBatchRow(file = null) {
  return { text: "", file, url: file ? URL.createObjectURL(file) : "", isCover: !!file };
}

function acceptBatchFile(file) {
  if (!IMAGE_TYPES.includes(file.type)) { showToast(`${file.name || "這張圖片"} 不是支援的 JPG、PNG、GIF 或 WebP`); return false; }
  if (file.size > 5 * 1024 * 1024) { showToast(`${file.name || "這張圖片"} 超過 5 MB`); return false; }
  return true;
}

function renderBatchRows() {
  batchRowsEl.textContent = "";
  batchRows.forEach((row, index) => {
    const el = document.createElement("div");
    el.className = "batch-row";
    const no = document.createElement("span");
    no.className = "batch-no";
    no.textContent = String(index + 1);
    const text = document.createElement("input");
    text.type = "text";
    text.placeholder = "書名或 ISBN（有附照片也可以留空）";
    text.value = row.text;
    text.addEventListener("input", () => { row.text = text.value; });
    const photo = document.createElement("div");
    photo.className = "batch-photo";
    if (row.file) {
      const image = document.createElement("img");
      image.src = row.url;
      image.alt = "書本照片";
      const cover = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = row.isCover;
      box.addEventListener("change", () => { row.isCover = box.checked; });
      cover.append(box, "這是封面");
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "batch-remove";
      clear.textContent = "×";
      clear.setAttribute("aria-label", "移除照片");
      clear.addEventListener("click", () => { URL.revokeObjectURL(row.url); row.file = null; row.url = ""; row.isCover = false; renderBatchRows(); });
      photo.append(image, cover, clear);
    } else {
      const pick = document.createElement("button");
      pick.type = "button";
      pick.className = "secondary";
      pick.textContent = "加照片";
      pick.addEventListener("click", () => {
        const chooser = document.createElement("input");
        chooser.type = "file";
        chooser.accept = IMAGE_TYPES.join(",");
        chooser.addEventListener("change", () => {
          const file = chooser.files[0];
          if (file && acceptBatchFile(file)) { row.file = file; row.url = URL.createObjectURL(file); row.isCover = true; renderBatchRows(); }
        });
        chooser.click();
      });
      photo.appendChild(pick);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "batch-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "移除這一本");
    remove.addEventListener("click", () => {
      if (row.url) URL.revokeObjectURL(row.url);
      batchRows.splice(index, 1);
      if (!batchRows.length) batchRows.push(newBatchRow());
      renderBatchRows();
    });
    el.append(no, text, photo, remove);
    batchRowsEl.appendChild(el);
  });
}

document.querySelector("#batch-button").addEventListener("click", () => {
  if (isResearching()) { showToast("請等目前的查證完成，或先按「停止」"); return; }
  if (!batchRows.length) batchRows = [newBatchRow(), newBatchRow()];
  renderBatchRows();
  batchDialog.showModal();
});
document.querySelector("#batch-add-row").addEventListener("click", () => {
  if (batchRows.length >= MAX_BATCH) { showToast(`一次最多 ${MAX_BATCH} 本`); return; }
  batchRows.push(newBatchRow());
  renderBatchRows();
});
document.querySelector("#batch-add-photos").addEventListener("click", () => batchPhotoInput.click());
batchPhotoInput.addEventListener("change", () => {
  // Each chosen photo becomes its own book row; untouched empty rows are dropped first.
  batchRows = batchRows.filter((row) => row.text.trim() || row.file);
  for (const file of batchPhotoInput.files) {
    if (batchRows.length >= MAX_BATCH) { showToast(`一次最多 ${MAX_BATCH} 本`); break; }
    if (acceptBatchFile(file)) batchRows.push(newBatchRow(file));
  }
  batchPhotoInput.value = "";
  if (!batchRows.length) batchRows.push(newBatchRow());
  renderBatchRows();
});

document.querySelector("#batch-start").addEventListener("click", async (event) => {
  event.preventDefault();
  const rows = batchRows.filter((row) => row.text.trim() || row.file);
  if (!rows.length) { showToast("請至少輸入一本書的書名、ISBN 或照片"); return; }
  const start = document.querySelector("#batch-start");
  start.disabled = true;
  try {
    const items = [];
    for (const row of rows) {
      const item = { text: row.text.trim(), isCover: row.isCover };
      if (row.file) item.image = { name: row.file.name, type: row.file.type, data: await fileToBase64(row.file) };
      items.push(item);
    }
    await api("/api/batch", { method: "POST", body: JSON.stringify({ items }) });
    batchRows.forEach((row) => row.url && URL.revokeObjectURL(row.url));
    batchRows = [];
    batchDialog.close();
  } catch (error) {
    showToast(error.message);
  } finally {
    start.disabled = false;
  }
});
