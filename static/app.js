const state = {
  notebooks: [],
  activeNotebookId: null,
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

async function loadHealth() {
  const health = await request("/api/health");
  renderRuntime(health);
}

async function loadNotebooks() {
  state.notebooks = await request("/api/notebooks");
  if (!state.activeNotebookId && state.notebooks.length > 0) {
    state.activeNotebookId = state.notebooks[0].id;
  }
  renderNotebookList();
  if (state.activeNotebookId) {
    await selectNotebook(state.activeNotebookId);
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
  if (!state.activeDesignSessionId && state.designSessions.length > 0) {
    state.activeDesignSessionId = state.designSessions[0].id;
  }

  renderDesignSessionList();

  if (state.activeDesignSessionId) {
    await selectDesignSession(state.activeDesignSessionId);
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

document.getElementById("upload-form").addEventListener("submit", (event) => {
  uploadSources(event).catch((error) => alert(error.message));
});

document.getElementById("chat-form").addEventListener("submit", (event) => {
  sendChat(event).catch((error) => alert(error.message));
});

document.getElementById("refresh-notebooks").addEventListener("click", () => {
  loadNotebooks().catch((error) => alert(error.message));
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
loadNotebooks().catch((error) => alert(error.message));
loadDesignSessions().catch((error) => alert(error.message));
