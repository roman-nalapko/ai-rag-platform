/* ── State ──────────────────────────────────────────────────────────────────── */
const state = {
  token: localStorage.getItem("rag_token") || "",
  userId: localStorage.getItem("rag_user_id") || "",
  userEmail: localStorage.getItem("rag_user_email") || "",
  knowledgeBaseId: localStorage.getItem("rag_kb_id") || "",
  conversationId: "",
};

/* ── DOM helpers ────────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);

function show(id) { $(id)?.classList.remove("hidden"); }
function hide(id) { $(id)?.classList.add("hidden"); }

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value || "—";
}

function setError(id, msg) {
  const el = $(id);
  if (!el) return;
  el.textContent = msg || "";
  msg ? el.classList.remove("hidden") : el.classList.add("hidden");
}

/* ── Logging ─────────────────────────────────────────────────────────────── */
function log(message, payload = null) {
  const timestamp = new Date().toISOString();
  const line = payload
    ? `${timestamp} ${message}\n${JSON.stringify(payload, null, 2)}`
    : `${timestamp} ${message}`;
  $("log").textContent = `${line}\n\n${$("log").textContent}`;
}

/* ── Auth helpers ────────────────────────────────────────────────────────── */
function authHeaders(extra = {}) {
  if (!state.token) throw new Error("Sign in first.");
  return { Authorization: `Bearer ${state.token}`, ...extra };
}

function saveSession(token, userId, email) {
  state.token = token;
  state.userId = userId;
  state.userEmail = email;
  localStorage.setItem("rag_token", token);
  localStorage.setItem("rag_user_id", userId);
  localStorage.setItem("rag_user_email", email);
}

function clearSession() {
  state.token = "";
  state.userId = "";
  state.userEmail = "";
  state.knowledgeBaseId = "";
  state.conversationId = "";
  localStorage.removeItem("rag_token");
  localStorage.removeItem("rag_user_id");
  localStorage.removeItem("rag_user_email");
  localStorage.removeItem("rag_kb_id");
}

/* ── Spinner helpers ─────────────────────────────────────────────────────── */
function withSpinner(spinnerId, btnId, fn) {
  return async (...args) => {
    const spinner = $(spinnerId);
    const btn = $(btnId);
    spinner?.classList.remove("hidden");
    if (btn) btn.disabled = true;
    try {
      await fn(...args);
    } finally {
      spinner?.classList.add("hidden");
      if (btn) btn.disabled = false;
    }
  };
}

/* ── HTTP helpers ─────────────────────────────────────────────────────────── */
async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload;
}

/* ── Rendering helpers ───────────────────────────────────────────────────── */
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c])
  );
}

function renderResults(containerId, results) {
  const container = $(containerId);
  container.innerHTML = "";
  if (!results?.length) {
    container.textContent = "No results yet.";
    return;
  }
  for (const result of results) {
    const item = document.createElement("div");
    item.className = "result";
    item.innerHTML = `
      <small>${escapeHtml(result.filename)} · chunk ${result.chunk_index} · score ${Number(result.score).toFixed(3)}</small>
      <p>${escapeHtml(result.content).slice(0, 700)}</p>
    `;
    container.appendChild(item);
  }
}

function requireKnowledgeBase() {
  if (!state.knowledgeBaseId) throw new Error("Select or create a knowledge base first.");
}

/* ── Auth gate UI ────────────────────────────────────────────────────────── */
function showApp() {
  hide("auth-gate");
  show("app");
  show("logout-btn");
  show("session-badge");
  const badge = $("session-badge");
  if (badge) badge.textContent = state.userEmail || state.userId.slice(0, 8) + "…";
}

function showAuthGate() {
  show("auth-gate");
  hide("app");
  hide("logout-btn");
  hide("session-badge");
}

/* ── Auth: Register ──────────────────────────────────────────────────────── */
$("form-register")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setError("register-error", "");
  const email = $("reg-email").value.trim();
  const password = $("reg-password").value;
  try {
    const token = await requestJson("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    // fetch user info — register returns token; decode user_id from JWT payload
    const userId = parseJwtUserId(token.access_token);
    saveSession(token.access_token, userId, email);
    log("Registered and signed in", { email });
    showApp();
    await initApp();
  } catch (error) {
    setError("register-error", error.message);
  }
});

/* ── Auth: Login ─────────────────────────────────────────────────────────── */
$("form-login")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  setError("login-error", "");
  const email = $("login-email").value.trim();
  const password = $("login-password").value;
  try {
    const token = await requestJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const userId = parseJwtUserId(token.access_token);
    saveSession(token.access_token, userId, email);
    log("Signed in", { email });
    showApp();
    await initApp();
  } catch (error) {
    setError("login-error", error.message);
  }
});

/* ── JWT userId extraction ───────────────────────────────────────────────── */
function parseJwtUserId(jwt) {
  try {
    const [, payload] = jwt.split(".");
    const padded = payload + "=".repeat((4 - payload.length % 4) % 4);
    const data = JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/")));
    return data.sub || "";
  } catch {
    return "";
  }
}

/* ── Auth tabs ───────────────────────────────────────────────────────────── */
$("tab-login")?.addEventListener("click", () => {
  $("tab-login").classList.add("active");
  $("tab-register").classList.remove("active");
  show("form-login");
  hide("form-register");
});

$("tab-register")?.addEventListener("click", () => {
  $("tab-register").classList.add("active");
  $("tab-login").classList.remove("active");
  hide("form-login");
  show("form-register");
});

/* ── Logout ──────────────────────────────────────────────────────────────── */
$("logout-btn")?.addEventListener("click", () => {
  clearSession();
  showAuthGate();
  log("Signed out");
});

/* ── Theme toggle ────────────────────────────────────────────────────────── */
const savedTheme = localStorage.getItem("rag_theme") || "dark";
document.documentElement.setAttribute("data-theme", savedTheme);
const themeBtn = $("theme-toggle");
if (themeBtn) themeBtn.textContent = savedTheme === "dark" ? "🌙" : "☀️";

$("theme-toggle")?.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("rag_theme", next);
  $("theme-toggle").textContent = next === "dark" ? "🌙" : "☀️";
});

/* ── Knowledge Bases ─────────────────────────────────────────────────────── */
async function loadKnowledgeBases() {
  if (!state.userId || !state.token) return;
  const kbs = await requestJson(`/knowledge-bases?user_id=${state.userId}&limit=100`, {
    headers: authHeaders(),
  });

  const select = $("kb-select");
  select.innerHTML = "";
  if (!kbs.length) {
    select.innerHTML = '<option value="">-- No knowledge bases found --</option>';
    select.disabled = true;
    state.knowledgeBaseId = "";
    localStorage.removeItem("rag_kb_id");
    setText("knowledge-base-id", "not selected");
    renderDocuments([]);
    return;
  }

  select.disabled = false;
  for (const kb of kbs) {
    const opt = document.createElement("option");
    opt.value = kb.id;
    opt.textContent = `${kb.name} (${kb.id.slice(0, 8)}…)`;
    select.appendChild(opt);
  }

  if (!state.knowledgeBaseId || !kbs.some((k) => k.id === state.knowledgeBaseId)) {
    select.value = kbs[0].id;
    state.knowledgeBaseId = kbs[0].id;
    localStorage.setItem("rag_kb_id", kbs[0].id);
  } else {
    select.value = state.knowledgeBaseId;
  }

  setText("knowledge-base-id", state.knowledgeBaseId);
  await loadDocuments();
  await loadConversations();
}

async function createKnowledgeBase() {
  if (!state.userId) throw new Error("Sign in first.");
  const name = $("kb-name").value.trim() || "AI RAG Platform Demo";
  const knowledgeBase = await requestJson("/knowledge-bases", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      user_id: state.userId,
      name,
      description: "Created from browser demo UI",
    }),
  });
  state.knowledgeBaseId = knowledgeBase.id;
  localStorage.setItem("rag_kb_id", knowledgeBase.id);
  setText("knowledge-base-id", knowledgeBase.id);
  log("Created knowledge base", knowledgeBase);
  await loadKnowledgeBases();
}

$("kb-select")?.addEventListener("change", async (e) => {
  state.knowledgeBaseId = e.target.value;
  localStorage.setItem("rag_kb_id", state.knowledgeBaseId);
  setText("knowledge-base-id", state.knowledgeBaseId || "not selected");
  state.conversationId = "";
  await loadDocuments();
  await loadConversations();
});

/* ── Documents ───────────────────────────────────────────────────────────── */
async function loadDocuments() {
  if (!state.knowledgeBaseId || !state.token) { renderDocuments([]); return; }
  const docs = await requestJson(
    `/documents?knowledge_base_id=${state.knowledgeBaseId}&limit=50`,
    { headers: authHeaders() }
  );
  renderDocuments(docs);
}

function renderDocuments(docs) {
  const container = $("document-list");
  container.innerHTML = "";
  if (!state.knowledgeBaseId) {
    container.innerHTML = '<p class="empty-state">Select or create a knowledge base to view documents.</p>';
    return;
  }
  if (!docs.length) {
    container.innerHTML = '<p class="empty-state">No documents uploaded yet. Upload a TXT or PDF file above.</p>';
    return;
  }

  for (const doc of docs) {
    const item = document.createElement("div");
    item.className = "doc-item";
    const statusBadge = `<span class="badge badge-${escapeHtml(doc.status)}">${escapeHtml(doc.status)}</span>`;
    item.innerHTML = `
      <div class="doc-info">
        <div class="doc-name">${escapeHtml(doc.filename)} ${statusBadge}</div>
        <div class="doc-meta">ID: ${doc.id} · Chunks: ${doc.chunks_count} · ${new Date(doc.created_at).toLocaleTimeString()}</div>
        ${doc.error_message ? `<div class="error" style="font-size:0.8rem">${escapeHtml(doc.error_message)}</div>` : ""}
      </div>
      <div class="doc-actions">
        <button class="secondary small-btn" onclick="window.reindexDoc('${doc.id}')">Reindex</button>
        <button class="danger small-btn" onclick="window.deleteDoc('${doc.id}')">Delete</button>
      </div>
    `;
    container.appendChild(item);
  }
}

window.reindexDoc = async (docId) => {
  try {
    const updated = await requestJson(`/documents/${docId}/reindex`, {
      method: "POST", headers: authHeaders(),
    });
    log("Reindexed document", updated);
    await loadDocuments();
  } catch (error) { log(`Reindex error: ${error.message}`); }
};

window.deleteDoc = async (docId) => {
  if (!confirm("Delete this document and its vectors?")) return;
  try {
    await requestJson(`/documents/${docId}`, { method: "DELETE", headers: authHeaders() });
    log(`Deleted document ${docId}`);
    await loadDocuments();
  } catch (error) { log(`Delete error: ${error.message}`); }
};

async function uploadDocument() {
  requireKnowledgeBase();
  const file = $("document-file").files[0];
  if (!file) throw new Error("Choose a TXT or PDF file.");
  const form = new FormData();
  form.append("knowledge_base_id", state.knowledgeBaseId);
  form.append("file", file);

  const doc = await requestJson("/documents/upload", {
    method: "POST", headers: authHeaders(), body: form,
  });
  log("Uploaded document, indexing queued", doc);
  $("document-file").value = "";
  await loadDocuments();

  let attempts = 0;
  const poller = setInterval(async () => {
    attempts += 1;
    await loadDocuments();
    if (attempts >= 6) clearInterval(poller);
  }, 2000);
}

/* ── Conversations ───────────────────────────────────────────────────────── */
async function loadConversations() {
  if (!state.knowledgeBaseId || !state.token) return;
  const convs = await requestJson(
    `/conversations?knowledge_base_id=${state.knowledgeBaseId}&limit=50`,
    { headers: authHeaders() }
  );

  const select = $("conv-select");
  select.innerHTML = '<option value="">-- Stateless QA (no history) --</option>';
  select.disabled = false;

  for (const conv of convs) {
    const opt = document.createElement("option");
    opt.value = conv.id;
    opt.textContent = `${conv.title || "Untitled Conversation"} (${conv.id.slice(0, 8)}…)`;
    select.appendChild(opt);
  }

  select.value = state.conversationId || "";
  setText("conversation-id", state.conversationId || "stateless");
}

async function createConversation() {
  requireKnowledgeBase();
  const title = prompt("Enter conversation title:", `Chat ${new Date().toLocaleTimeString()}`);
  if (title === null) return;

  const conv = await requestJson("/conversations", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ knowledge_base_id: state.knowledgeBaseId, title: title || "Demo Chat" }),
  });
  state.conversationId = conv.id;
  log("Created conversation", conv);
  await loadConversations();
}

$("conv-select")?.addEventListener("change", (e) => {
  state.conversationId = e.target.value;
  setText("conversation-id", state.conversationId || "stateless");
});

/* ── Search ──────────────────────────────────────────────────────────────── */
async function runSearch() {
  requireKnowledgeBase();
  const query = $("search-query").value.trim();
  if (!query) throw new Error("Enter a search query.");
  const hybrid = $("search-hybrid")?.checked || false;

  const search = await requestJson("/search", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ knowledge_base_id: state.knowledgeBaseId, query, limit: 5, hybrid }),
  });
  renderResults("search-results", search.results);
  log(hybrid ? "Hybrid search (RRF) completed" : "Semantic vector search completed", {
    query, result_count: search.results.length,
  });
}

/* ── QA ──────────────────────────────────────────────────────────────────── */
async function askQuestion() {
  requireKnowledgeBase();
  const question = $("question").value.trim();
  if (!question) throw new Error("Enter a question.");
  const hybrid = $("qa-hybrid")?.checked || false;

  const payload = { knowledge_base_id: state.knowledgeBaseId, question, limit: 5, hybrid };
  if (state.conversationId) payload.conversation_id = state.conversationId;

  const qa = await requestJson("/qa/ask", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  $("answer").textContent = qa.answer;
  renderResults("sources", qa.sources);
  log(hybrid ? "Hybrid QA completed" : "QA completed", { question, source_count: qa.sources.length });
}

async function streamQuestion() {
  requireKnowledgeBase();
  const question = $("question").value.trim();
  if (!question) throw new Error("Enter a question.");
  const hybrid = $("qa-hybrid")?.checked || false;

  $("answer").textContent = "";
  $("sources").innerHTML = "<p class='empty-state'>Retrieving relevant chunks…</p>";

  const payload = { knowledge_base_id: state.knowledgeBaseId, question, limit: 5, hybrid };
  if (state.conversationId) payload.conversation_id = state.conversationId;

  const response = await fetch("/qa/ask/stream", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Streaming failed with HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const rawEvent of events) {
      if (!rawEvent.trim()) continue;
      const lines = rawEvent.split("\n");
      let eventType = "message";
      const dataLines = [];
      for (const line of lines) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
      }
      const dataStr = dataLines.join("\n");
      if (eventType === "sources") {
        try { renderResults("sources", JSON.parse(dataStr)); } catch {}
      } else if (eventType === "token" || eventType === "message") {
        if (dataStr === "[DONE]") { log("Streaming QA response finished"); return; }
        $("answer").textContent += dataStr;
      } else if (eventType === "done") {
        log("Streaming QA completed", dataStr);
      }
    }
  }
}

/* ── Button bindings ─────────────────────────────────────────────────────── */
function bind(id, handler) {
  const el = $(id);
  if (!el) return;
  el.addEventListener("click", async () => {
    try { await handler(); }
    catch (error) {
      log(`Error: ${error.message}`);
      const logEl = $("log");
      logEl?.classList.add("error");
      setTimeout(() => logEl?.classList.remove("error"), 800);
    }
  });
}

bind("create-kb", createKnowledgeBase);
bind("refresh-kbs", loadKnowledgeBases);
bind("upload-document", withSpinner("upload-spinner", "upload-document", uploadDocument));
bind("refresh-docs", loadDocuments);
bind("create-conv", createConversation);
bind("refresh-convs", loadConversations);
bind("run-search", withSpinner("search-spinner", "run-search", runSearch));
bind("ask-question", withSpinner("ask-spinner", "ask-question", askQuestion));
bind("stream-question", withSpinner("stream-spinner", "stream-question", streamQuestion));
bind("clear-log", () => { $("log").textContent = ""; });
bind("copy-log", async () => {
  try {
    await navigator.clipboard.writeText($("log").textContent);
    log("Log copied to clipboard");
  } catch { log("Clipboard not available — select and copy manually"); }
});

/* ── App init ────────────────────────────────────────────────────────────── */
async function initApp() {
  if (state.knowledgeBaseId) {
    setText("knowledge-base-id", state.knowledgeBaseId);
    const select = $("kb-select");
    if (select) select.value = state.knowledgeBaseId;
  }
  await loadKnowledgeBases();
}

/* ── Bootstrap ───────────────────────────────────────────────────────────── */
if (state.token) {
  showApp();
  initApp().catch((err) => {
    // Token may have expired — drop session and go back to login
    if (err.message.includes("401") || err.message.includes("expired")) {
      clearSession();
      showAuthGate();
    } else {
      log(`Init error: ${err.message}`);
    }
  });
} else {
  showAuthGate();
}
