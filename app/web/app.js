const state = {
  token: "",
  userId: "",
  knowledgeBaseId: "",
  documentId: "",
};

const $ = (id) => document.getElementById(id);

function log(message, payload = null) {
  const timestamp = new Date().toISOString();
  const line = payload
    ? `${timestamp} ${message}\n${JSON.stringify(payload, null, 2)}`
    : `${timestamp} ${message}`;
  $("log").textContent = `${line}\n\n${$("log").textContent}`;
}

function setText(id, value) {
  $(id).textContent = value || "—";
}

function authHeaders(extra = {}) {
  if (!state.token) {
    throw new Error("Create a demo token first.");
  }
  return {
    Authorization: `Bearer ${state.token}`,
    ...extra,
  };
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function requireKnowledgeBase() {
  if (!state.knowledgeBaseId) {
    throw new Error("Create a knowledge base first.");
  }
}

function renderResults(containerId, results) {
  const container = $(containerId);
  container.innerHTML = "";
  if (!results.length) {
    container.textContent = "No results yet.";
    return;
  }
  for (const result of results) {
    const item = document.createElement("div");
    item.className = "result";
    item.innerHTML = `
      <small>${result.filename} · chunk ${result.chunk_index} · score ${Number(result.score).toFixed(3)}</small>
      <p>${escapeHtml(result.content).slice(0, 700)}</p>
    `;
    container.appendChild(item);
  }
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return entities[character];
  });
}

async function createUserAndToken() {
  const email = $("email").value.trim();
  const user = await requestJson("/users", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({email}),
  });
  state.userId = user.id;
  setText("user-id", user.id);

  const token = await requestJson("/auth/demo-token", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({user_id: user.id}),
  });
  state.token = token.access_token;
  setText("token-status", `${token.token_type}, expires in ${token.expires_in}s`);
  log("Created user and demo token", {user});
}

async function createKnowledgeBase() {
  if (!state.userId) {
    throw new Error("Create a user first.");
  }
  const knowledgeBase = await requestJson("/knowledge-bases", {
    method: "POST",
    headers: authHeaders({"Content-Type": "application/json"}),
    body: JSON.stringify({
      user_id: state.userId,
      name: $("kb-name").value.trim() || "AI RAG Platform Demo",
      description: "Created from the browser demo UI",
    }),
  });
  state.knowledgeBaseId = knowledgeBase.id;
  setText("knowledge-base-id", knowledgeBase.id);
  log("Created knowledge base", knowledgeBase);
}

async function uploadDocument() {
  requireKnowledgeBase();
  const file = $("document-file").files[0];
  if (!file) {
    throw new Error("Choose a TXT or PDF file.");
  }
  const form = new FormData();
  form.append("knowledge_base_id", state.knowledgeBaseId);
  form.append("file", file);
  const document = await requestJson("/documents/upload", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  state.documentId = document.id;
  setText("document-id", document.id);
  setText("document-status", document.status);
  log("Uploaded document", document);
}

async function pollDocument() {
  if (!state.documentId) {
    throw new Error("Upload a document first.");
  }
  const document = await requestJson(`/documents/${state.documentId}`, {
    headers: authHeaders(),
  });
  setText("document-status", `${document.status} · chunks=${document.chunks_count}`);
  log("Document status", document);
}

async function runSearch() {
  requireKnowledgeBase();
  const search = await requestJson("/search", {
    method: "POST",
    headers: authHeaders({"Content-Type": "application/json"}),
    body: JSON.stringify({
      knowledge_base_id: state.knowledgeBaseId,
      query: $("search-query").value,
      limit: 5,
    }),
  });
  renderResults("search-results", search.results);
  log("Semantic search completed", search);
}

async function askQuestion() {
  requireKnowledgeBase();
  const qa = await requestJson("/qa/ask", {
    method: "POST",
    headers: authHeaders({"Content-Type": "application/json"}),
    body: JSON.stringify({
      knowledge_base_id: state.knowledgeBaseId,
      question: $("question").value,
      limit: 5,
    }),
  });
  $("answer").textContent = qa.answer;
  renderResults("sources", qa.sources);
  log("QA completed", qa);
}

async function streamQuestion() {
  requireKnowledgeBase();
  $("answer").textContent = "";
  $("sources").textContent = "Streaming endpoint returns tokens first; use normal Ask to inspect sources.";
  const response = await fetch("/qa/ask/stream", {
    method: "POST",
    headers: authHeaders({
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    }),
    body: JSON.stringify({
      knowledge_base_id: state.knowledgeBaseId,
      question: $("question").value,
      limit: 5,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Streaming failed with HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const event of events) {
      const data = event
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))
        .join("\n");
      if (data === "[DONE]") {
        log("Streaming QA completed");
        return;
      }
      $("answer").textContent += data;
    }
  }
}

function bind(id, handler) {
  $(id).addEventListener("click", async () => {
    try {
      await handler();
    } catch (error) {
      log(`Error: ${error.message}`);
      $("log").classList.add("error");
      setTimeout(() => $("log").classList.remove("error"), 600);
    }
  });
}

bind("create-user", createUserAndToken);
bind("create-kb", createKnowledgeBase);
bind("upload-document", uploadDocument);
bind("poll-document", pollDocument);
bind("run-search", runSearch);
bind("ask-question", askQuestion);
bind("stream-question", streamQuestion);
