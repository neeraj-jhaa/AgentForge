# ⌁ AgentForge — Multi-Agent Task Orchestration Platform

AgentForge is a control room for a small team of specialist AI agents — a
**Planner**, **Researcher**, **Coder**, **Critic**, and **Synthesizer** —
coordinated by a supervisor orchestrator to complete open-ended goals.
Give it a task in plain English; watch the agents plan it, execute it with
real tools (live web search, sandboxed Python execution, a calculator),
critique their own work, revise it, and merge everything into one polished
answer — streamed live to a mission-control style UI.

![status](https://img.shields.io/badge/status-portfolio_project-F5A623)
![python](https://img.shields.io/badge/python-3.11-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---


<a href = "https://agentforge-t2d5.onrender.com" > AGENTFORGE</a>



## Why this project (and not another chatbot wrapper)

Most "AI agent" portfolio projects are a single LLM call with a system
prompt. AgentForge demonstrates the parts of agentic systems that actually
come up in AI engineering interviews:

- **Multi-agent orchestration** — a supervisor graph that plans, routes
  work to specialists, critiques, revises, and synthesizes, not a single
  prompt-response loop.
- **Real tool use** — an OpenAI-style tool-calling loop implemented
  from scratch (`agents/base.py`): model → tool call → tool execution →
  tool result fed back → repeat, with a hard round limit. Runs against
  Groq's free-tier, tool-calling-capable models via the OpenAI SDK.
- **Retrieval-augmented memory** — a lightweight TF-IDF vector store
  that lets later tasks recall relevant context from earlier ones, with
  an interface designed to swap in a real embedding model later.
- **Streaming, observable execution** — every agent thought, tool call,
  and tool result is streamed over a WebSocket and persisted to SQLite
  for replay, not just a final blob of text.
- **Production shape** — Dockerized, environment-configured, health-
  checked, with a sandboxed (timeout + denylist) code execution tool
  instead of a bare `eval`.

---

## Architecture

```
                         ┌─────────────────────┐
                         │   Supervisor /       │
      user goal  ──────► │   Orchestrator        │
                         │  (orchestrator.py)    │
                         └──────────┬────────────┘
                                    │
                 ┌──────────────────┼───────────────────┐
                 ▼                  ▼                    ▼
          ┌─────────────┐   ┌──────────────┐     ┌──────────────┐
          │   Planner    │   │  Researcher /  │     │    Critic     │
          │ (decomposes) │   │     Coder      │────►│  (reviews)    │
          └─────────────┘   │ (executes steps)│     └───────┬──────┘
                 │           └──────┬─────────┘              │
                 │                  │  tools:                │ revise if
                 │                  │  web_search             │ not approved
                 │                  │  execute_python          │
                 │                  │  calculator               ▼
                 │                  │                    ┌──────────────┐
                 └─────────────────►│                    │  Synthesizer  │
                                    │                    │ (final answer)│
                                    ▼                    └──────┬───────┘
                          ┌──────────────────┐                  │
                          │  Semantic Memory   │◄─────────────────┘
                          │  (TF-IDF store)     │   writes outcome
                          └──────────────────┘   for future recall

  Every agent's thoughts / tool calls / tool results stream live over a
  WebSocket to the frontend and are written to SQLite for full replay.
```

**Backend:** FastAPI + WebSocket, `openai` Python SDK pointed at Groq's
OpenAI-compatible endpoint, SQLite, scikit-learn (TF-IDF memory),
BeautifulSoup (search parsing).

**Frontend:** Zero-build vanilla HTML/CSS/JS (no npm toolchain to fight
with in Docker) with a live-updating agent roster, an animated pipeline
strip, and a streaming console — served directly by FastAPI as static
files, so the whole app is one container.

---

## Quick start (Docker — recommended)

```bash
git clone <this-repo> agentforge && cd agentforge
cp .env.example .env
# edit .env and paste your free Groq API key (console.groq.com/keys)

docker compose up --build
```

Open **http://localhost:8000**.

## Quick start (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** (the FastAPI app serves `frontend/static`
directly — no separate frontend server needed).

---

## Try it

- *"Research the current landscape of small modular reactors and summarize the top 3 companies."*
- *"Write and verify a Python function that checks whether a number is prime, then benchmark it against a naive loop."*
- *"Compare REST and GraphQL for a mobile app with intermittent connectivity and justify a recommendation."*

Watch the pipeline strip light up as the goal moves through
**Plan → Research/Code → Critique → Synthesize**, and check the sidebar
for which agent is currently active and which tools it's calling.

---

## Project layout

```
agentforge/
├── backend/
│   └── app/
│       ├── agents/
│       │   ├── base.py          # tool-use loop shared by every agent
│       │   └── specialists.py   # Planner / Researcher / Coder / Critic / Synthesizer
│       ├── tools/
│       │   ├── web_search.py    # DuckDuckGo HTML search, no API key needed
│       │   ├── code_executor.py # sandboxed subprocess Python runner
│       │   └── calculator.py    # safe AST-based arithmetic (no eval)
│       ├── memory/
│       │   └── vector_store.py  # TF-IDF semantic memory (RAG)
│       ├── orchestrator.py      # supervisor graph: plan→execute→critique→synthesize
│       ├── database.py          # SQLite persistence (tasks, events, memory)
│       ├── config.py            # env-driven settings
│       └── main.py              # FastAPI app + WebSocket endpoint
├── frontend/static/             # zero-build HTML/CSS/JS control-room UI
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Extending it (good talking points for an interview)

- **Swap providers**: everything goes through `BASE_URL` +
  `GROQ_API_KEY` in `config.py` via the OpenAI SDK, so pointing at
  real OpenAI, Together.ai, Fireworks, or self-hosted vLLM is just an
  env var change — no code touches the provider directly except
  `agents/base.py`. Note Groq's free tier has request-per-minute
  limits; if you hit them mid-task, the run will surface an API error
  in that agent's console card.
- **Swap the memory backend**: `memory/vector_store.py` exposes
  `add()` / `search()`; replacing TF-IDF with real embeddings
  (OpenAI, Voyage, sentence-transformers) or a vector DB (Chroma,
  Qdrant, pgvector) is a one-file change.
- **Smarter routing**: `orchestrator._route_step()` is a keyword
  heuristic today; swap it for a small routing model call for
  dynamic, learned delegation.
- **Parallel execution**: steps currently execute sequentially; an
  `asyncio.gather` over independent steps would parallelize the
  Research/Code stage.
- **Real sandboxing**: `code_executor.py` uses a denylist + subprocess
  timeout; production would use gVisor/Firecracker/nsjail or a
  managed code-execution API.
- **Auth & multi-tenant tasks**: add a user/session layer in front of
  the WebSocket and scope `tasks`/`memory` tables by user.

---

## Resume bullet points (edit to taste, only claim what you actually ran)

- Designed and built a multi-agent orchestration platform (Planner /
  Researcher / Coder / Critic / Synthesizer) coordinating specialist
  LLM agents through a supervisor graph with tool use, self-critique,
  and automatic revision loops.
- Implemented an OpenAI-style tool-calling loop from scratch (model →
  tool call → execution → result feedback) against Groq's free-tier
  inference API, powering three tools: live web search, sandboxed
  Python execution, and safe arithmetic evaluation.
- Built a lightweight retrieval-augmented memory layer (TF-IDF vector
  search) giving the agent system long-term recall across tasks
  without external infra dependencies.
- Shipped a real-time streaming UI (FastAPI WebSockets + vanilla JS)
  visualizing live agent reasoning, tool calls, and a mission-control
  style execution pipeline.
- Containerized the full stack with Docker / docker-compose,
  including health checks and environment-driven configuration for
  portable deployment.

---

## License

MIT — build on it freely.
