# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ClaraSeg is a Portuguese-language conversational customer-service agent demo for "Vivaz Seguros" (a fictional
insurer), built to demonstrate LangGraph + MongoDB Atlas Vector Search + MCP. The agent ("Clara") answers
questions about policy coverage and claim status, keeps short- and long-term memory of the customer, does
semantic search over policy clauses, and can call out to an external MCP tool server for partner-workshop
lookup and inspection scheduling.

Repo layout:
| Directory | Contents |
|---|---|
| `ai-agent/` | Agent backend: LangGraph graph, memory, tools, `src/` package, smoke tests, FastAPI HTTP API (`src/api.py`, own Dockerfile/requirements) |
| `workshop-mcp/` | Standalone MCP server simulating a partner workshop network (own Dockerfile/requirements) |
| `webapp/` | React SPA (Vite) — talks to `ai-agent` (`/health`, `/chat/stream`) and `customer-api` (`/clients*`) over HTTP/SSE only, never imports `ai-agent/src` or touches Mongo directly; own Dockerfile (multi-stage build, served by nginx) |
| `customer-api/` | Standalone Node.js/Express backend, read-only against `customer_profile` (`GET /clients`, `GET /clients/{id}`) for the React UI's sidebar/profile modal; own Dockerfile, reuses the root `.env` for Mongo credentials |
| `data/` | DB seeding (`seed.py`, seed JSON) and the PDF ingestion pipeline (`ingestion/ingest.py`, `source_docs/`) |
| `specifications/` | Original agent/interface specs |
| `documentation/` | Setup guide, technical writeup, business context, demo script |

## Commands

Run from the repo root unless noted. A `.venv` (Python 3.14) already exists; activate it or call `.venv/bin/python` directly.

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env   # fill MONGODB_URI, OPENAI_API_KEY, etc.

# Seed customer_profile + workshops collections from static JSON
python data/seed.py

# Ingest policy PDFs into policy_chunks (Docling -> chunk -> embed -> Mongo)
# First run downloads Docling layout models (several GB) -- do this ahead of a live demo.
python data/ingestion/ingest.py --input-dir data/source_docs

# Run the workshop MCP server (either)
docker compose up workshop-mcp                 # dockerized, streamable-http on :8000
python workshop-mcp/workshop_server.py         # local, same transport/port

# Run the customer-api backend (either) -- reads MONGODB_URI/MONGODB_DB_NAME from the root .env
docker compose up customer-api                 # dockerized, on :8090
cd customer-api && npm install && npm run dev  # local, same routes

# Run the webapp (React + Vite) -- needs ai-agent (:8080) and customer-api (:8090) running
docker compose up webapp                       # dockerized (nginx serving a prod build), on :5173
cd webapp && npm install && npm run dev        # local, dev server with HMR on :5173

# Run the agent HTTP API (either)
docker compose up ai-agent                                          # dockerized, on :8080
cd ai-agent && uvicorn src.api:app --reload --port 8080              # local, same routes

# End-to-end smoke tests -- MUST be run with cwd=ai-agent/ (relies on `from src...` imports)
cd ai-agent && python -m tests.test_agent_smoke
```

There is no linter/formatter or unit test framework configured — `ai-agent/tests/test_agent_smoke.py` is a
manual, assertion-based script run directly (not via pytest) that exercises 8 acceptance criteria end to end
against real OpenAI + MongoDB Atlas; it takes 90-120s and costs real API calls.

The Atlas Vector Search index cannot be created programmatically via pymongo — it must be created manually in
the Atlas UI on the target collection's `embedding` field (1536 dims, cosine), with `metadata.category` as a
filter field, named to match `VECTOR_INDEX_NAME` in `.env`.

## Architecture

**Coupling point:** everything that goes through the LangGraph agent is reached through
`ai-agent/src/agent.invoke(thread_id, customer_id, message) -> dict` (and its streaming counterpart,
`agent.astream`) — all graph/memory/tool complexity is encapsulated behind those two functions, which is what
`ai-agent/src/api.py` (`/chat`, `/chat/stream`) wraps for the React UI's chat and transparency panel. Read-only
listing/lookup of customer profiles for the sidebar and profile modal does **not** go through the agent at all
— it's served by the separate `customer-api/` Node.js backend, which queries `customer_profile` directly and by
design has zero knowledge of the graph, tools, or memory layers. The webapp only ever talks HTTP to these two
backends; it never imports `ai-agent/src` or connects to Mongo itself.

`agent.py` is async internally — it opens a `MultiServerMCPClient` (HTTP transport, `WORKSHOP_MCP_URL`) to fetch
MCP tools, builds the graph, and calls `graph.ainvoke(...)` — but `invoke()` is a sync wrapper (`asyncio.run(...)`)
so `api.py`'s `POST /chat` handler (a plain sync `def`) can call it directly. The graph is rebuilt on every call
(cheap — just Python object construction) because the MCP tool list is fetched fresh each time.

**`ai-agent/src/api.py`** is a second, thinner caller of the same module: a FastAPI app with `GET /health`
(pings Mongo), `POST /chat` (wraps `agent.invoke`), and `POST /chat/stream` (wraps `agent.astream`, an SSE
generator added alongside `invoke`). Token-level streaming works by filtering `graph.astream_events()` for
`on_chat_model_stream` events tagged `ANSWER_LLM_TAG` (`src/graph/nodes.py`) — that tag exists specifically to
distinguish the main answer LLM call from the second, untagged fact-extraction call that `reasoning` also
makes on the same node; without it the two calls' token streams would be indistinguishable. The graph-building
step in `astream` is inside the `try` block (unlike a plain `ainvoke`) so an MCP connection failure surfaces as
an `{"type": "error"}` SSE event instead of killing the HTTP stream. Runs containerized via
`ai-agent/Dockerfile` — its `requirements.txt` deliberately excludes `docling` (ingestion-only) to keep the
serving image lean; in `docker-compose.yml` it overrides `WORKSHOP_MCP_URL`/`POLICY_MCP_URL` to the sibling
containers' service names since `localhost` doesn't resolve across containers.

**LangGraph flow** (`ai-agent/src/graph/build.py`):

```
START -> load_memory -> reasoning --[tools_condition]--> tools_node -> reasoning (loop)
                                    \--[no tool calls]--> save_memory -> END
```

- `load_memory` and `save_memory` are fixed nodes: they run unconditionally every turn.
- `reasoning` <-> `tools_node` is a loop: the LLM can chain multiple tool calls (e.g. look up a clause, then
  look up a workshop) within a single customer turn before producing a final answer.
- State (`ai-agent/src/graph/state.py`, a `TypedDict`): `customer_id`, `messages` (reducer `add_messages`,
  the full conversation tape including `ToolMessage`s), `long_term_facts`, `customer_profile`,
  `new_fact_to_save` (a one-shot channel from `reasoning` to `save_memory`).

**Tools all live in one `ToolNode`** (`ai-agent/src/graph/build.py`): the local `vector_search_clausulas`
function and the remote MCP tools (`buscar_oficinas_proximas`, `consultar_agenda_pericia`, `agendar_pericia`,
`listar_agendamentos_cliente`, `cancelar_agendamento`, `alterar_agendamento`) are dispatched identically by
name — the graph has no notion of "local" vs "remote" tool.

**Two independent memory layers**, both backed by MongoDB, on different keys:
- *Short-term* — `MongoDBSaver` checkpointer, collection `short_term_memory`, keyed by
  `thread_id = "{customer_id}_{uuid_hex[:8]}"`. LangGraph restores `messages` from this checkpoint
  automatically on every invocation; the app never resends history. A new `thread_id` = blank history.
- *Long-term* — `MongoDBStore`, collection `long_term_memory`, namespace `(customer_id, "facts")`,
  independent of `thread_id` — survives across sessions. Populated by a **second** LLM call the `reasoning`
  node makes after producing a final answer (no tool calls pending), which classifies whether the turn
  contained a new durable fact (`EXTRACT_FACT_PROMPT` in `ai-agent/src/graph/nodes.py`) and returns structured
  JSON (`{"has_fact": ..., "key": ..., "fact": ...}`).

**`workshop-mcp/workshop_server.py`** is a deliberately self-contained `FastMCP` server (streamable-http
transport, port 8000) — it imports nothing from `ai-agent/src`, has its own minimal `requirements.txt`, and
reads its Mongo connection straight from env vars, so it can be built/deployed as an independent Docker image
simulating a real third-party partner system. It operates on the `workshops` collection, where each workshop
document embeds its own `appointments` array (a customer may only have one open appointment at a time —
enforced in `agendar_pericia`).

**PDF ingestion** (`data/ingestion/ingest.py`) is a separate pipeline from `data/seed.py`: it walks
category-named subfolders under an input dir (e.g. `auto/`, `residencial/`, `vida/`), converts each PDF with
Docling, chunks structurally with `HybridChunker` (using a real OpenAI tokenizer, not a HF model name), embeds
with `text-embedding-3-small`, and upserts into MongoDB keyed by `sha256(source_file + chunk_text)` for
idempotency. Chunks under `MIN_CHUNK_CHARS` (200 chars) are discarded — Docling sometimes emits orphan
heading-only chunks (e.g. a bare "Cláusula 5.1" label) or table-of-contents chunks with no real content;
`ai-agent/src/tools/vector_search.py` applies the same `MIN_CHUNK_CHARS` filter at query time via `$match`
after `$vectorSearch`, as a second line of defense. `data/seed.py` is unrelated — it just loads
`customer_profile` and `workshops` from static seed JSON.

## Data model (MongoDB, db name = `MONGODB_DB_NAME`, default `claraseg`)

| Collection | Managed by | Notes |
|---|---|---|
| `short_term_memory` | LangGraph `MongoDBSaver` | Internal schema — don't edit manually |
| `long_term_memory` | LangGraph `MongoDBStore` | Internal schema — don't edit manually |
| `policy_chunks` | `data/ingestion/ingest.py` | Clause chunks + embeddings; needs the manual Atlas Vector Search index |
| `customer_profile` | `data/seed.py` + `customer-api` | Customer policies/claims (`policies`, `claims` fields drive the system prompt's claim-lookup logic); read-only by `customer-api` for the React UI |
| `workshops` | `data/seed.py` + `workshop-mcp` | Partner workshops; `appointments` embedded per workshop doc |

## Key conventions

- **Cross-directory imports are path-hacked, not packaged.** `ai-agent/src` is not pip-installed; `data/seed.py`
  prepends `ai-agent/` to `sys.path` at the top of the file so `from src...` resolves, which is why it can be
  run from the repo root. `ai-agent/tests/test_agent_smoke.py` has no such shim, so it must be run with
  `cwd=ai-agent/`. `webapp/` (React) and `customer-api/` (Node.js) are separate language ecosystems entirely —
  they never import from `ai-agent/src`, only call it over HTTP.
- **The system prompt is the primary behavior-control surface**, not a config file — it's a large string in
  `ai-agent/src/graph/nodes.py`. It enforces a strict paragraph structure for claim/accident-related replies
  (acknowledgement -> related-claim lookup in `customer_profile.claims` -> tool-sourced technical answer ->
  next-step offer) and explicitly forbids reusing a tool result from an earlier turn to answer a new message,
  even a rephrased one — every qualifying new message must re-trigger the relevant tool.
- **Tool docstrings drive model behavior, not just documentation.** The LLM reads them to decide when/how to
  call a tool (e.g. `vector_search_clausulas`'s docstring in `ai-agent/src/tools/vector_search.py`) — editing
  a docstring is a behavioral change.
- **MCP transport is HTTP**, not stdio: `ai-agent/src/tools/mcp_client.py` configures
  `MultiServerMCPClient` with `transport: "http"` against `WORKSHOP_MCP_URL`, and `workshop-mcp` runs as its
  own long-lived process/container rather than a subprocess spawned per request.
- **`documentation/*.md` predates the current MCP/tooling setup** — README.md, SETUP.md and TECHNICAL.md
  describe an stdio MCP subprocess with only two workshop tools (`buscar_oficinas_proximas`,
  `consultar_agenda_pericia`) and a `policy_clauses` collection with one clause per document. The actual code
  uses HTTP/streamable-http MCP, six workshop tools (scheduling: `agendar_pericia`, `listar_agendamentos_cliente`,
  `cancelar_agendamento`, `alterar_agendamento`), a third "vida" (life insurance) policy category, and a
  `policy_chunks` collection populated by the Docling ingestion pipeline. Treat the source code as
  authoritative over these docs for architecture questions; `documentation/context.md` (business context) and
  `documentation/DEMO_SCRIPT.md` (presenter script) are still accurate.
