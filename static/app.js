const state = {
  notebooks: [],
  activeNotebookId: null,
  settings: null,
  designSessions: [],
  activeDesignSessionId: null,
  activeDesignArtifactId: null,
};

const runtimeStatus = document.getElementById("runtime-status");
const notebookItems = document.getElementById("notebook-items");
const sourceList = document.getElementById("source-list");
const chatLog = document.getElementById("chat-log");
const studioOutput = document.getElementById("studio-output");
const activeNotebookTitle = document.getElementById("active-notebook-title");
const activeNotebookDescription = document.getElementById("active-notebook-description");
const renameNotebookTitle = document.getElementById("rename-notebook-title");
const renameNotebookDescription = document.getElementById("rename-notebook-description");

const settingsScreen = document.getElementById("settings-screen");
const settingsStatus = document.getElementById("settings-status");
const settingsFields = {
  host: document.getElementById("settings-host"),
  port: document.getElementById("settings-port"),
  chunk_size: document.getElementById("settings-chunk-size"),
  chunk_overlap: document.getElementById("settings-chunk-overlap"),
  retrieval_top_k: document.getElementById("settings-top-k"),
  embedding_provider: document.getElementById("settings-embedding-provider"),
  embedding_model: document.getElementById("settings-embedding-model"),
  embedding_threads: document.getElementById("settings-embedding-threads"),
  embedding_device: document.getElementById("settings-embedding-device"),
  embedding_cache_dir: document.getElementById("settings-embedding-cache-dir"),
  llama_base_url: document.getElementById("settings-llama-base-url"),
  llama_model: document.getElementById("settings-llama-model"),
  llama_timeout: document.getElementById("settings-llama-timeout"),
  llama_api_key: document.getElementById("settings-llama-api-key"),
  ocr_provider: document.getElementById("settings-ocr-provider"),
  ocr_languages: document.getElementById("settings-ocr-languages"),
  stt_provider: document.getElementById("settings-stt-provider"),
  whisper_model: document.getElementById("settings-whisper-model"),
  whisper_device: document.getElementById("settings-whisper-device"),
  whisper_compute_type: document.getElementById("settings-whisper-compute-type"),
};

const designSessionItems = document.getElementById("design-session-items");
const designSessionMeta = document.getElementById("design-session-meta");
const advisorOutput = document.getElementById("advisor-output");
const critiqueOutput = document.getElementById("critique-output");
const designPreview = document.getElementById("design-preview");
const artifactDirection = document.getElementById("artifact-direction");

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderRuntime(health) {
  const llama = health.llama || {};
  const embeddings = health.embeddings || {};
  const feature = health.features || {};
  runtimeStatus.innerHTML = `
    <div><strong>llama.cpp</strong>: ${llama.reachable ? "online" : "offline"}</div>
    <div><strong>Embeddings</strong>: ${embeddings.provider || "-"}</div>
    <div><strong>Embedding Model</strong>: ${embeddings.model || "-"}</div>
    <div><strong>OCR</strong>: ${feature.ocr_provider || "-"}</div>
    <div><strong>STT</strong>: ${feature.stt_provider || "-"}</div>
    <div><strong>Whisper</strong>: ${feature.whisper_model || "-"}</div>
    <div><strong>Chunking</strong>: ${feature.chunk_size || "-"} / ${feature.chunk_overlap || "-"}</div>
    <div><strong>Top K</strong>: ${feature.retrieval_top_k || "-"}</div>
  `;
}

function renderNotebookList() {
  notebookItems.innerHTML = "";
  const template = document.getElementById("notebook-item-template");

  for (const notebook of state.notebooks) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".item-title").textContent = notebook.title;
    node.querySelector(".item-description").textContent = notebook.description || "沒有描述";
    if (notebook.id === state.activeNotebookId) {
      node.classList.add("active");
    }
    node.addEventListener("click", () => {
      selectNotebook(notebook.id).catch((error) => alert(error.message));
    });
    notebookItems.appendChild(node);
  }
}

function renderSources(sources) {
  sourceList.innerHTML = "";
  const template = document.getElementById("source-item-template");

  for (const source of sources) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".source-name").textContent = source.filename;
    node.querySelector(".source-status").textContent = source.status;

    const meta = source.metadata || {};
    const parts = [
      `kind: ${meta.kind || source.kind}`,
      `chunks: ${meta.chunk_count ?? 0}`,
      `chars: ${meta.text_characters ?? 0}`,
    ];

    if (meta.embedding_model) {
      parts.push(`embedding: ${meta.embedding_model}`);
    }
    if (meta.error) {
      parts.push(`error: ${meta.error}`);
      node.classList.add("error");
    }
    node.querySelector(".source-meta").textContent = parts.join(" | ");
    sourceList.appendChild(node);
  }
}

function renderMessages(messages) {
  chatLog.innerHTML = "";
  const template = document.getElementById("message-template");

  for (const message of messages) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.classList.add(message.role);
    node.querySelector(".message-role").textContent = message.role === "user" ? "你" : "JNotebookLM";
    node.querySelector(".message-content").innerHTML = escapeHtml(message.content).replaceAll("\n", "<br>");

    const citationsRoot = node.querySelector(".citations");
    for (const citation of message.citations || []) {
      const badge = document.createElement("span");
      badge.className = "citation";
      badge.textContent = `${citation.source_name} #${citation.chunk_index}`;
      citationsRoot.appendChild(badge);
    }
    chatLog.appendChild(node);
  }

  chatLog.scrollTop = chatLog.scrollHeight;
}

function syncNotebookManageFields(notebook) {
  if (!notebook) {
    renameNotebookTitle.value = "";
    renameNotebookDescription.value = "";
    return;
  }
  renameNotebookTitle.value = notebook.title || "";
  renameNotebookDescription.value = notebook.description || "";
}

function clearNotebookDetailView() {
  activeNotebookTitle.textContent = "先建立或選擇一個 Notebook";
  activeNotebookDescription.textContent = "中欄專注對話，回答會依左側來源檢索結果產生。";
  sourceList.innerHTML = "";
  chatLog.innerHTML = "";
  syncNotebookManageFields(null);
}

function openSettings() {
  settingsScreen.classList.remove("hidden");
  settingsScreen.setAttribute("aria-hidden", "false");
}

function closeSettings() {
  settingsScreen.classList.add("hidden");
  settingsScreen.setAttribute("aria-hidden", "true");
}

function renderSettings(payload) {
  state.settings = payload.settings || null;
  const settings = payload.settings || {};
  for (const [key, field] of Object.entries(settingsFields)) {
    if (!(key in settings)) {
      continue;
    }
    const value = settings[key];
    field.value = Array.isArray(value) ? value.join(",") : value;
  }

  const restartFields = payload.restart_required_fields || [];
  const restartNote = restartFields.length > 0 ? ` 需要重啟：${restartFields.join(", ")}` : "";
  settingsStatus.textContent = (payload.note || "設定已載入。") + restartNote;
}

async function loadHealth() {
  const health = await request("/api/health");
  renderRuntime(health);
}

async function loadSettings() {
  const payload = await request("/api/settings");
  renderSettings(payload);
}

async function loadNotebooks() {
  state.notebooks = await request("/api/notebooks");
  const activeExists = state.notebooks.some((item) => item.id === state.activeNotebookId);
  if (!state.activeNotebookId && state.notebooks.length > 0) {
    state.activeNotebookId = state.notebooks[0].id;
  } else if (!activeExists) {
    state.activeNotebookId = state.notebooks.length > 0 ? state.notebooks[0].id : null;
  }
  renderNotebookList();
  if (state.activeNotebookId) {
    await selectNotebook(state.activeNotebookId);
  } else {
    clearNotebookDetailView();
  }
}

async function selectNotebook(notebookId) {
  state.activeNotebookId = notebookId;
  renderNotebookList();

  const notebook = await request(`/api/notebooks/${notebookId}`);
  activeNotebookTitle.textContent = notebook.title;
  activeNotebookDescription.textContent = notebook.description || "沒有描述";
  renderSources(notebook.sources || []);
  renderMessages(notebook.messages || []);
  syncNotebookManageFields(notebook);
}

async function createNotebook(event) {
  event.preventDefault();

  const title = document.getElementById("notebook-title").value.trim();
  const description = document.getElementById("notebook-description").value.trim();
  if (!title) {
    return;
  }

  const notebook = await request("/api/notebooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });

  document.getElementById("create-notebook-form").reset();
  state.activeNotebookId = notebook.id;
  await loadNotebooks();
}

async function renameNotebook(event) {
  event.preventDefault();
  if (!state.activeNotebookId) {
    alert("請先選擇 notebook");
    return;
  }

  const title = renameNotebookTitle.value.trim();
  const description = renameNotebookDescription.value.trim();
  if (!title) {
    alert("名稱不能為空");
    return;
  }

  await request(`/api/notebooks/${state.activeNotebookId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });

  await loadNotebooks();
}

async function deleteNotebook() {
  if (!state.activeNotebookId) {
    alert("請先選擇 notebook");
    return;
  }

  const target = state.notebooks.find((item) => item.id === state.activeNotebookId);
  const label = target?.title || "這本 notebook";
  const confirmed = window.confirm(`確定要刪除「${label}」嗎？此動作無法復原。`);
  if (!confirmed) {
    return;
  }

  await request(`/api/notebooks/${state.activeNotebookId}`, {
    method: "DELETE",
  });

  state.activeNotebookId = null;
  await loadNotebooks();
}

async function uploadSources(event) {
  event.preventDefault();
  if (!state.activeNotebookId) {
    alert("請先建立 notebook");
    return;
  }

  const filesInput = document.getElementById("source-files");
  if (!filesInput.files.length) {
    return;
  }

  const formData = new FormData();
  for (const file of filesInput.files) {
    formData.append("files", file);
  }

  await request(`/api/notebooks/${state.activeNotebookId}/sources`, {
    method: "POST",
    body: formData,
  });

  filesInput.value = "";
  await selectNotebook(state.activeNotebookId);
}

async function sendChat(event) {
  event.preventDefault();
  if (!state.activeNotebookId) {
    alert("請先建立 notebook");
    return;
  }

  const questionField = document.getElementById("chat-question");
  const question = questionField.value.trim();
  if (!question) {
    return;
  }

  questionField.value = "";
  await request(`/api/notebooks/${state.activeNotebookId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  await selectNotebook(state.activeNotebookId);
}

async function generateNotebookStudio(mode) {
  if (!state.activeNotebookId) {
    alert("請先建立 notebook");
    return;
  }

  const payload = await request(`/api/notebooks/${state.activeNotebookId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });

  studioOutput.textContent = payload.warning
    ? `${payload.warning}\n\n${payload.content}`
    : payload.content;
}

async function saveSettings(event) {
  event.preventDefault();
  settingsStatus.textContent = "儲存中...";

  const payload = {
    host: settingsFields.host.value.trim(),
    port: Number(settingsFields.port.value),
    chunk_size: Number(settingsFields.chunk_size.value),
    chunk_overlap: Number(settingsFields.chunk_overlap.value),
    retrieval_top_k: Number(settingsFields.retrieval_top_k.value),
    embedding_provider: settingsFields.embedding_provider.value.trim(),
    embedding_model: settingsFields.embedding_model.value.trim(),
    embedding_threads: Number(settingsFields.embedding_threads.value),
    embedding_device: settingsFields.embedding_device.value.trim(),
    embedding_cache_dir: settingsFields.embedding_cache_dir.value.trim(),
    llama_base_url: settingsFields.llama_base_url.value.trim(),
    llama_model: settingsFields.llama_model.value.trim(),
    llama_timeout: Number(settingsFields.llama_timeout.value),
    llama_api_key: settingsFields.llama_api_key.value.trim(),
    ocr_provider: settingsFields.ocr_provider.value.trim(),
    ocr_languages: settingsFields.ocr_languages.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    stt_provider: settingsFields.stt_provider.value.trim(),
    whisper_model: settingsFields.whisper_model.value.trim(),
    whisper_device: settingsFields.whisper_device.value.trim(),
    whisper_compute_type: settingsFields.whisper_compute_type.value.trim(),
  };

  const response = await request("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  renderSettings(response);
  await loadHealth();
}

function renderDesignSessionList() {
  designSessionItems.innerHTML = "";
  const template = document.getElementById("design-session-item-template");

  for (const session of state.designSessions) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".item-title").textContent = session.name;
    node.querySelector(".item-description").textContent = session.brief.slice(0, 80);

    if (session.id === state.activeDesignSessionId) {
      node.classList.add("active");
    }

    node.addEventListener("click", () => {
      selectDesignSession(session.id).catch((error) => alert(error.message));
    });
    designSessionItems.appendChild(node);
  }
}

function renderDesignArtifacts(detail) {
  const container = document.getElementById("design-artifact-items");
  container.innerHTML = "";
  const template = document.getElementById("design-artifact-item-template");

  for (const artifact of detail.artifacts || []) {
    const node = template.content.firstElementChild.cloneNode(true);
    node.querySelector(".item-title").textContent = `${artifact.artifact_type} · ${artifact.title}`;
    node.querySelector(".item-description").textContent = artifact.preview_text || "(無預覽文字)";

    if (artifact.id === state.activeDesignArtifactId) {
      node.classList.add("active");
    }

    node.addEventListener("click", () => {
      selectDesignArtifact(artifact.id).catch((error) => alert(error.message));
    });
    container.appendChild(node);
  }
}

async function loadDesignSessions() {
  state.designSessions = await request("/api/design/sessions");
  const activeExists = state.designSessions.some((item) => item.id === state.activeDesignSessionId);
  if (!state.activeDesignSessionId && state.designSessions.length > 0) {
    state.activeDesignSessionId = state.designSessions[0].id;
  } else if (!activeExists) {
    state.activeDesignSessionId = state.designSessions.length > 0 ? state.designSessions[0].id : null;
  }

  renderDesignSessionList();

  if (state.activeDesignSessionId) {
    await selectDesignSession(state.activeDesignSessionId);
  } else {
    designSessionMeta.textContent = "";
    designPreview.srcdoc = "";
  }
}

async function selectDesignSession(sessionId) {
  state.activeDesignSessionId = sessionId;
  renderDesignSessionList();

  const detail = await request(`/api/design/sessions/${sessionId}`);
  designSessionMeta.textContent = `workspace: ${detail.workspace_path}`;

  renderDesignArtifacts(detail);

  if (detail.artifacts && detail.artifacts.length > 0) {
    const exists = detail.artifacts.some((artifact) => artifact.id === state.activeDesignArtifactId);
    if (!exists) {
      state.activeDesignArtifactId = detail.artifacts[0].id;
    }
    await selectDesignArtifact(state.activeDesignArtifactId);
  } else {
    state.activeDesignArtifactId = null;
    designPreview.srcdoc = "";
  }
}

async function createDesignSession(event) {
  event.preventDefault();

  const name = document.getElementById("design-name").value.trim();
  const brief = document.getElementById("design-brief").value.trim();
  const language = document.getElementById("design-language").value.trim() || "zh-Hant";

  if (!name || !brief) {
    return;
  }

  const session = await request("/api/design/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, brief, language }),
  });

  document.getElementById("design-create-form").reset();
  document.getElementById("design-language").value = "zh-Hant";
  state.activeDesignSessionId = session.id;
  await loadDesignSessions();
}

async function runDesignAdvisor() {
  if (!state.activeDesignSessionId) {
    alert("請先建立 Design Session");
    return;
  }

  const goal = document.getElementById("advisor-goal").value.trim();
  const response = await request(`/api/design/sessions/${state.activeDesignSessionId}/advisor`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal }),
  });

  const lines = [response.summary, ""];
  for (const [index, direction] of (response.directions || []).entries()) {
    lines.push(
      `${index + 1}. ${direction.name}`,
      `   philosophy: ${direction.philosophy}`,
      `   palette: ${(direction.palette || []).join(", ")}`,
      `   typography: ${direction.typography}`,
      `   rationale: ${direction.rationale}`,
      `   focus: ${direction.scene_focus}`,
      ""
    );
  }
  if (response.warning) {
    lines.push(`warning: ${response.warning}`);
  }

  advisorOutput.textContent = lines.join("\n");

  if (!artifactDirection.value.trim() && response.directions && response.directions.length > 0) {
    artifactDirection.value = response.directions[0].name;
  }
}

async function generateDesignArtifact(event) {
  event.preventDefault();
  if (!state.activeDesignSessionId) {
    alert("請先建立 Design Session");
    return;
  }

  const artifactType = document.getElementById("artifact-type").value;
  const directionName = document.getElementById("artifact-direction").value.trim();
  const requirements = document.getElementById("artifact-requirements").value.trim();

  const artifact = await request(`/api/design/sessions/${state.activeDesignSessionId}/artifacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      artifact_type: artifactType,
      direction_name: directionName,
      requirements,
    }),
  });

  state.activeDesignArtifactId = artifact.id;
  await selectDesignSession(state.activeDesignSessionId);
}

async function selectDesignArtifact(artifactId) {
  if (!state.activeDesignSessionId || !artifactId) {
    return;
  }

  state.activeDesignArtifactId = artifactId;

  const payload = await request(
    `/api/design/sessions/${state.activeDesignSessionId}/artifacts/${artifactId}/content`
  );

  designPreview.srcdoc = payload.content || "";

  const detail = await request(`/api/design/sessions/${state.activeDesignSessionId}`);
  renderDesignArtifacts(detail);
}

async function runDesignCritique() {
  if (!state.activeDesignSessionId || !state.activeDesignArtifactId) {
    alert("請先選擇一個 artifact");
    return;
  }

  const focus = document.getElementById("critique-focus").value.trim();
  const response = await request(
    `/api/design/sessions/${state.activeDesignSessionId}/artifacts/${state.activeDesignArtifactId}/critique`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ focus }),
    }
  );

  const lines = [response.overview, "", "Dimensions:"];
  for (const dim of response.dimensions || []) {
    lines.push(`- ${dim.name}: ${dim.score}/10 · ${dim.note}`);
  }

  lines.push("", "Keep:");
  for (const item of response.keep || []) {
    lines.push(`- ${item}`);
  }

  lines.push("", "Fix:");
  for (const item of response.fix || []) {
    lines.push(`- ${item}`);
  }

  lines.push("", "Quick wins:");
  for (const item of response.quick_wins || []) {
    lines.push(`- ${item}`);
  }

  if (response.warning) {
    lines.push("", `warning: ${response.warning}`);
  }

  critiqueOutput.textContent = lines.join("\n");
}

async function applyDesignTweaks() {
  if (!state.activeDesignSessionId || !state.activeDesignArtifactId) {
    alert("請先選擇一個 artifact");
    return;
  }

  const raw = document.getElementById("tweaks-json").value.trim();
  if (!raw) {
    return;
  }

  let values;
  try {
    values = JSON.parse(raw);
  } catch (_error) {
    alert("Tweaks JSON 格式錯誤");
    return;
  }

  await request(
    `/api/design/sessions/${state.activeDesignSessionId}/artifacts/${state.activeDesignArtifactId}/tweaks`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    }
  );

  await selectDesignArtifact(state.activeDesignArtifactId);
}

document.getElementById("create-notebook-form").addEventListener("submit", (event) => {
  createNotebook(event).catch((error) => alert(error.message));
});

document.getElementById("rename-notebook-form").addEventListener("submit", (event) => {
  renameNotebook(event).catch((error) => alert(error.message));
});

document.getElementById("delete-notebook").addEventListener("click", () => {
  deleteNotebook().catch((error) => alert(error.message));
});

document.getElementById("upload-form").addEventListener("submit", (event) => {
  uploadSources(event).catch((error) => alert(error.message));
});

document.getElementById("chat-form").addEventListener("submit", (event) => {
  sendChat(event).catch((error) => alert(error.message));
});

document.getElementById("settings-form").addEventListener("submit", (event) => {
  saveSettings(event).catch((error) => {
    settingsStatus.textContent = error.message;
  });
});

document.getElementById("refresh-notebooks").addEventListener("click", () => {
  loadNotebooks().catch((error) => alert(error.message));
});

document.getElementById("open-settings").addEventListener("click", () => {
  openSettings();
  loadSettings().catch((error) => {
    settingsStatus.textContent = error.message;
  });
});

document.getElementById("close-settings").addEventListener("click", () => {
  closeSettings();
});

settingsScreen.addEventListener("click", (event) => {
  if (event.target === settingsScreen) {
    closeSettings();
  }
});

for (const button of document.querySelectorAll("[data-generate]")) {
  button.addEventListener("click", () => {
    generateNotebookStudio(button.dataset.generate).catch((error) => alert(error.message));
  });
}

document.getElementById("design-create-form").addEventListener("submit", (event) => {
  createDesignSession(event).catch((error) => alert(error.message));
});

document.getElementById("refresh-design-sessions").addEventListener("click", () => {
  loadDesignSessions().catch((error) => alert(error.message));
});

document.getElementById("artifact-form").addEventListener("submit", (event) => {
  generateDesignArtifact(event).catch((error) => alert(error.message));
});

document.getElementById("run-advisor").addEventListener("click", () => {
  runDesignAdvisor().catch((error) => alert(error.message));
});

document.getElementById("run-critique").addEventListener("click", () => {
  runDesignCritique().catch((error) => alert(error.message));
});

document.getElementById("apply-tweaks").addEventListener("click", () => {
  applyDesignTweaks().catch((error) => alert(error.message));
});

loadHealth().catch((error) => {
  runtimeStatus.textContent = error.message;
});
loadSettings().catch((error) => {
  settingsStatus.textContent = error.message;
});
loadNotebooks().catch((error) => alert(error.message));
loadDesignSessions().catch((error) => alert(error.message));
