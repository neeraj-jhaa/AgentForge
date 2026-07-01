/* AgentForge frontend — WebSocket client + live console renderer */

const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/task";

const el = {
  console: document.getElementById("console"),
  consoleEmpty: document.getElementById("consoleEmpty"),
  composer: document.getElementById("composer"),
  goalInput: document.getElementById("goalInput"),
  sendBtn: document.getElementById("sendBtn"),
  connDot: document.getElementById("connDot"),
  connLabel: document.getElementById("connLabel"),
  historyList: document.getElementById("historyList"),
  resultBody: document.getElementById("resultBody"),
  pipeline: document.getElementById("pipeline"),
};

const PIPE_STAGE = {
  planner: 0, researcher: 1, coder: 1, critic: 2, synthesizer: 3,
};

let ws;
let taskRunning = false;

function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    el.connDot.className = "conn-dot live";
    el.connLabel.textContent = "connected";
  };
  ws.onclose = () => {
    el.connDot.className = "conn-dot down";
    el.connLabel.textContent = "reconnecting…";
    setTimeout(connect, 1500);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    handleEvent(event);
  };
}
connect();

function setAgentActive(agentName, on) {
  document.querySelectorAll(`.agent-card[data-agent="${agentName}"] .agent-dot`).forEach(d => {
    d.classList.toggle("on", on);
  });
}

function setPipelineStage(agentName) {
  const stage = PIPE_STAGE[agentName];
  if (stage === undefined) return;
  const nodes = el.pipeline.querySelectorAll(".pipe-node");
  const lines = el.pipeline.querySelectorAll(".pipe-line");
  nodes.forEach((n, i) => n.classList.toggle("active", i <= stage));
  lines.forEach((l, i) => l.classList.toggle("active", i < stage));
}

function resetPipeline() {
  el.pipeline.querySelectorAll(".pipe-node, .pipe-line").forEach(n => n.classList.remove("active"));
}

function addEventCard(event) {
  el.consoleEmpty.style.display = "none";
  const card = document.createElement("div");
  card.className = "event-card";
  card.dataset.agent = event.agent;
  card.dataset.kind = event.kind;

  const head = document.createElement("div");
  head.className = "event-head";
  head.innerHTML = `<span class="event-agent">${event.agent}</span><span class="event-kind">${labelForKind(event.kind)}</span>`;

  const body = document.createElement("div");
  body.className = "event-body";
  body.textContent = event.content;

  card.appendChild(head);
  card.appendChild(body);
  el.console.appendChild(card);
  el.console.scrollTop = el.console.scrollHeight;
}

function labelForKind(kind) {
  return {
    thought: "reasoning",
    tool_call: "→ tool call",
    tool_result: "← tool result",
    output: "step output",
    error: "error",
    task_started: "task started",
    done: "complete",
  }[kind] || kind;
}

function handleEvent(event) {
  if (event.kind === "task_started") {
    taskRunning = true;
    el.sendBtn.disabled = true;
    resetPipeline();
    return;
  }

  if (event.agent && PIPE_STAGE[event.agent] !== undefined) {
    setAgentActive(event.agent, true);
    setPipelineStage(event.agent);
  } else if (event.agent === "memory") {
    setAgentActive("memory", true);
  }

  addEventCard(event);

  if (event.kind === "done") {
    taskRunning = false;
    el.sendBtn.disabled = false;
    el.resultBody.innerHTML = marked.parse(event.content || "*(no output)*");
    document.querySelectorAll(".agent-dot").forEach(d => d.classList.remove("on"));
    refreshHistory();
  }
  if (event.kind === "error" && !taskRunning) {
    el.sendBtn.disabled = false;
  }
}

el.composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const goal = el.goalInput.value.trim();
  if (!goal || taskRunning) return;
  if (ws.readyState !== WebSocket.OPEN) return;

  el.console.innerHTML = "";
  el.resultBody.innerHTML = '<div class="result-placeholder">Working…</div>';
  ws.send(JSON.stringify({ goal }));
  el.goalInput.value = "";
});

async function refreshHistory() {
  try {
    const res = await fetch("/api/tasks");
    const tasks = await res.json();
    el.historyList.innerHTML = "";
    tasks.slice(0, 12).forEach(t => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `<div class="h-status ${t.status}">${t.status}</div><div>${escapeHtml(t.goal).slice(0, 60)}</div>`;
      item.onclick = () => loadTask(t.id);
      el.historyList.appendChild(item);
    });
  } catch (e) { /* backend not reachable yet */ }
}

async function loadTask(taskId) {
  const res = await fetch(`/api/tasks/${taskId}`);
  const task = await res.json();
  el.console.innerHTML = "";
  el.consoleEmpty.style.display = "none";
  (task.events || []).forEach(ev => addEventCard(ev));
  el.resultBody.innerHTML = marked.parse(task.result || "*(no result yet)*");
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

refreshHistory();
