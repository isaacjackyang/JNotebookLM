const state = {
  notebooks: [],
  activeNotebookId: null,
};

const runtimeStatus = document.getElementById("runtime-status");
const notebookItems = document.getElementById("notebook-items");
const sourceList = document.getElementById("source-list");
const chatLog = document.getElementById("chat-log");
const studioOutput = document.getElementById("studio-output");
const activeNotebookTitle = document.getElementById("active-notebook-title");
const activeNotebookDescription = document.getElementById("active-notebook-description");

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function escapeHtml(text) {
  return text
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
    node.addEventListener("click", () => selectNotebook(notebook.id));
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

async function generate(mode) {
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
    generate(button.dataset.generate).catch((error) => alert(error.message));
  });
}

loadHealth().catch((error) => {
  runtimeStatus.textContent = error.message;
});
loadNotebooks().catch((error) => alert(error.message));
