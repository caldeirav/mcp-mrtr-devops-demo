# mcp-mrtr-devops-demo

End-to-end demo of **Multi Round-Trip Requests (MRTR)** under **MCP SEP-2322**, using LangGraph, agentgateway, LM Studio, and Spec-Kit in Cursor IDE.

Stateless human-in-the-loop (HITL) DevOps agent: yield for confirmation, resume on any server instance, no sticky SSE sessions.

## Executive summary

This repository demonstrates a production-shaped pattern for mid-call HITL under the **2026-07-28 MCP specification**. When an agent hits a destructive operation, the MCP server returns a signed continuation handle and closes the connection. The client pauses, collects operator input, then resubmits—routable to any backend behind a load balancer.

## Use case: emergency database migration agent

An autonomous DevOps AI agent receives a prompt to run an emergency migration on production cluster `prod-db-01`. The migration file `V004__drop_legacy_users.sql` contains destructive operations (`DROP TABLE`).

Before executing, the agent must obtain human authorization. Under MRTR, that pause is **stateless**: no open SSE GET stream and no in-memory paused thread on a specific pod.

## Legacy bottleneck (pre-2026 / e.g. MCP 2025-11-25)

Older MCP HITL patterns typically required:

- Open, persistent **Server-Sent Events (SSE) GET** streams for mid-call authorization
- An MCP server that **held the execution thread** in memory while waiting for user confirmation

**Failure mode:** If an API gateway or load balancer dropped the idle SSE socket—or server pods auto-scaled—the paused thread died, agent state was lost, and operators had to restart the whole flow manually.

## How MRTR (SEP-2322) resolves it

Under the **2026-07-28** MCP specification (SEP-2322):

1. **Stateless yield** — On a destructive operation, the MCP server does **not** hold a connection open. It packages the user input schema (`inputRequests`) and an **HMAC-signed** continuation token (`requestState`), returns HTTP 200 with `resultType: "input_required"`, and terminates the socket immediately.
2. **Non-blocking client pause** — The LangGraph client receives `input_required`, pauses its graph, and releases system resources.
3. **Stateless resubmission** — The operator completes the confirmation prompt (UI/terminal). LangGraph re-issues `tools/call` as an HTTP POST with `inputResponses` and the echoed `requestState`.
4. **Unpinned load balancing** — Round-robin via **agentgateway** can route the retry to **any** available server instance. That instance validates the HMAC, runs the migration, and returns `resultType: "complete"`.

`Mcp-Session-Id` and sticky session headers are **not** used.

## Technical stack

| Layer | Choice |
| --- | --- |
| IDE / orchestration | Cursor IDE + GitHub Spec-Kit (`specify-cli`) |
| Agent framework | LangGraph (Python) — workflow state, non-blocking pauses, retry loops |
| LLM | LM Studio — `qwen/qwen3.6-35b-a3b` at `http://127.0.0.1:1234/v1` |
| API gateway / L7 | agentgateway — Streamable HTTP proxy on port **8080** (`statefulMode: stateless`) |
| MCP protocol | MCP **2026-07-28** stateless core + SEP-2322 MRTR payloads |

## Architecture (logical)

```text
Operator terminal
        │
        ▼
main.py (harness)
   ├── validates LM Studio :1234
   ├── starts MCP server   :8000
   └── starts agentgateway :8080
        │
        ▼
LangGraph agent ── tools/call ──► agentgateway :8080 ──► MCP server :8000
        │                                                 │
        │◄── input_required + requestState ───────────────┤
        │                                                 │
   terminal HITL (confirm_drop + environment_tag)         │
        │                                                 │
        └── retry + inputResponses + requestState ────────┘
                              │
                              ▼
                    resultType: complete
```

## End-to-end setup and run

Follow these steps in order on macOS or Linux.

### Step 0 — Prerequisites checklist

| Requirement | Why |
| --- | --- |
| Python **3.11+** | Runtime for MCP server, agent, and harness |
| [`uv`](https://github.com/astral-sh/uv) | Installs deps and runs the project |
| [LM Studio](https://lmstudio.ai/) | Local OpenAI-compatible LLM |
| Model `qwen/qwen3.6-35b-a3b` (or matching `MODEL_NAME`) | Used by the LangGraph agent |
| [`agentgateway`](https://agentgateway.dev/docs/standalone/latest/deployment/binary) on `PATH` | L7 proxy for tool calls (constitution: no gateway bypass) |
| Free local ports **1234**, **8000**, **8080** | LLM, MCP server, agentgateway |
| Port **15000** free (optional) | agentgateway admin UI / LLM playground |
| [Docker](https://docs.docker.com/get-docker/) (optional) | Jaeger traces for pause/resume screenshots |

### Step 1 — Clone the repository

```bash
git clone https://github.com/caldeirav/mcp-mrtr-devops-demo.git
cd mcp-mrtr-devops-demo
```

(Or open the existing checkout and `cd` into the repo root.)

### Step 2 — Install `uv` (if needed)

```bash
# macOS (Homebrew)
brew install uv

# or official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Confirm:

```bash
uv --version
python3 --version   # should be 3.11+
```

### Step 3 — Install agentgateway

```bash
curl -sL https://agentgateway.dev/install | bash
agentgateway --version
```

Ensure the binary is on your `PATH` (the installer typically places it in `/usr/local/bin`).

### Step 4 — Start LM Studio and load the model

1. Open **LM Studio**.
2. Download / select model **`qwen/qwen3.6-35b-a3b`** (or the id you will put in `.env` as `MODEL_NAME`).
3. Start the **local server** (OpenAI-compatible API) on **`http://127.0.0.1:1234`**.
4. Confirm the server is up (LM Studio UI shows listening, or):

```bash
curl -s http://127.0.0.1:1234/v1/models | head
```

You should see JSON listing available models. Leave LM Studio running for the rest of the demo.

### Step 5 — Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```bash
OPENAI_API_BASE=http://127.0.0.1:1234/v1
OPENAI_API_KEY=lm-studio
MODEL_NAME=qwen/qwen3.6-35b-a3b
AGENTGATEWAY_PORT=8080
MCP_SERVER_PORT=8000
MCP_HMAC_SECRET=<long-random-secret>
ENABLE_JAEGER=0
```

Keep `MODEL_NAME` aligned with `llm.models[].params.model` in `agentgateway.yaml`.  
LangGraph chat uses LM Studio **directly** (`OPENAI_API_BASE`); the gateway `llm` block is for the **admin UI playground**, not agent chat.

Generate a secret if you do not have one:

```bash
# example: 64 hex chars
openssl rand -hex 32
```

Paste the value into `MCP_HMAC_SECRET`. Do **not** commit `.env` (it is gitignored).

### Step 6 — Install Python dependencies

From the repo root:

```bash
uv sync --group dev
```

This creates `.venv` and installs `langgraph`, `fastapi`, `httpx`, and the rest of the stack (see `pyproject.toml`).

### Step 7 — (Optional) Run automated tests

These do **not** require agentgateway or a live demo session (integration test skips if gateway is down):

```bash
uv run pytest
```

Expect unit/contract tests to pass.

### Step 8 — Run the end-to-end demo

One command starts MCP, agentgateway, validates the LLM, and runs the agent:

```bash
uv run python main.py
```

What the harness does automatically:

1. Fail-fast check that LM Studio answers at `OPENAI_API_BASE`
2. Ensures `agentgateway.yaml` exists (`statefulMode: stateless`, `:8080` → MCP `:8000/mcp`, plus `llm` + OTLP tracing)
3. If `ENABLE_JAEGER=1`, starts or reuses Docker Jaeger (`:16686` UI / `:4317` OTLP); warns and continues if Docker/Jaeger fails
4. Starts the MCP server on `MCP_SERVER_PORT` (default **8000**)
5. Starts `agentgateway -f agentgateway.yaml` on **8080** with `OPENAI_API_KEY` in the process env (logs → `.demo_logs/`)
6. Runs the LangGraph agent for defaults **`prod-db-01`** / **`V004__drop_legacy_users.sql`**
7. On Ctrl+C / exit, stops MCP + agentgateway; if the harness started Jaeger for this run, it `docker stop`s (does not `rm`) that container

Terminal output is banded so you can tell layers apart:

| Band | Meaning |
| --- | --- |
| `TRACE` | Harness / LangGraph / HTTP execution |
| `AGENT` | LLM narrative and packaged answers |
| `HITL` | Your operator prompts (no open SSE socket) |
| `SEP` | Detailed request/response + ★ what changed in 2026-07-28 / SEP-2322 |

`SEP` panels highlight new fields (`resultType`, `requestState`, `inputRequests` / `inputResponses`, per-request `_meta`, `Mcp-Method` / `Mcp-Name`) and call out removed sticky-session behavior (`Mcp-Session-Id` absent). Set `NO_COLOR=1` to disable ANSI colors.

While the harness is running (or with MCP + agentgateway started manually), you can also drive the same gateway from the **admin UI** — see [Demo steps in the agentgateway UI](#demo-steps-in-the-agentgateway-ui) below. That path is ideal for screenshots; the LangGraph terminal path remains the primary HITL story.

### Step 9 — Complete the human-in-the-loop prompts

When the destructive migration is detected you will see a terminal block similar to:

```text
=== Human-in-the-loop authorization required ===
Confirm destructive migration ...
confirm_drop [true/false]:
environment_tag ['dev', 'staging', 'prod']:
```

Happy-path answers:

```text
confirm_drop [true/false]: true
environment_tag ['dev', 'staging', 'prod']: prod
```

Then the agent retries through agentgateway with `inputResponses` + echoed `requestState` and prints a **`complete`** summary (simulated apply).

**Other useful answers to try**

| Input | Expected outcome |
| --- | --- |
| `confirm_drop=false` | `complete` with denied/cancelled text; migration not applied |
| `environment_tag=qa` | `complete` with denied text (tag outside allow-list) |
| Wait longer than **5 minutes** before answering | Resume fails (expired `requestState`) |

### Step 10 — Shut down

Press `Ctrl+C` if the process is still running. The harness tears down MCP and agentgateway. You can quit LM Studio when finished.

---

## Demo steps in the agentgateway UI

Use this walkthrough for **screenshots and audience demos** of the gateway layer. It complements (does not replace) the LangGraph terminal HITL in Steps 8–9.

**Prerequisites for UI demos**

| Need | Check |
| --- | --- |
| MCP + agentgateway up | `uv run python main.py` **or** start MCP + `agentgateway -f agentgateway.yaml` with `OPENAI_API_KEY` in the gateway env |
| LM Studio serving the demo model | `curl -s http://127.0.0.1:1234/v1/models` returns your model |
| Config valid | `export OPENAI_API_KEY=lm-studio && agentgateway -f agentgateway.yaml --validate-only` |
| CORS for the admin origin | `agentgateway.yaml` allows `http://localhost:15000` |

**Ports**

| Port | Service |
| --- | --- |
| `1234` | LM Studio OpenAI API |
| `8000` | MCP server |
| `8080` | agentgateway MCP proxy |
| `15000` | agentgateway admin UI |
| `4317` | OTLP gRPC (Jaeger, optional) |
| `16686` | Jaeger UI (optional) |

Contract / quickstart detail: [specs/002-gateway-llm-tracing/quickstart.md](specs/002-gateway-llm-tracing/quickstart.md).

---

### UI Step 1 — Open the admin console

1. Browse to **[http://localhost:15000/ui/](http://localhost:15000/ui/)**.
2. Confirm the UI loads (blank/error page usually means agentgateway is not running or port `15000` is blocked).
3. Optionally open the architecture / targets view and confirm target **`devops-migration`** points at the local MCP upstream (`http://127.0.0.1:8000/mcp`) with **stateless** MCP mode (no sticky session pinning).

---

### UI Step 2 — Tool Playground: list `apply_db_migration`

This shows the gateway can discover tools from the MCP server (same path the LangGraph agent uses via `:8080`).

1. In the admin UI, open **Tool Playground** (or the MCP tools / playground section — label may vary slightly by agentgateway version).
2. Select target / server **`devops-migration`** if prompted.
3. Refresh or list tools.
4. Confirm tool **`apply_db_migration`** appears with arguments `cluster_id` and `script_name`.

If the list is empty or you see a protocol-version error, restart agentgateway with the repo `agentgateway.yaml` and ensure the MCP server is healthy on `:8000`.

---

### UI Step 3 — Tool Playground: destructive call → `input_required`

Demonstrate SEP-2322 MRTR **without** the LangGraph terminal (great for a slide).

1. In Tool Playground, choose **`apply_db_migration`**.
2. Set arguments:
   - `cluster_id`: `prod-db-01`
   - `script_name`: `V004__drop_legacy_users.sql`
3. Send / invoke the tool.
4. Inspect the JSON result. You should see:
   - top-level **`resultType`: `"input_required"`**
   - **`requestState`** (HMAC continuation handle)
   - **`inputRequests`** with a form asking for `confirm_drop` and `environment_tag`
5. Call out to the audience: the HTTP response finished; there is **no** open SSE GET and **no** `Mcp-Session-Id` required to continue later.

**Screenshot tip:** Capture the `input_required` payload with `resultType` and `requestState` visible.

---

### UI Step 4 — Tool Playground: resume → `complete` (optional)

If the UI supports filling elicitation / `inputResponses` on retry:

1. Resubmit the same tool with the same `cluster_id` / `script_name`.
2. Include the echoed **`requestState`** from Step 3.
3. Provide acceptance answers, e.g. `confirm_drop: true`, `environment_tag: "prod"`.
4. Confirm **`resultType`: `"complete"`** and a simulated apply summary.

If the playground UI does not yet expose a clean resume form, switch to the **LangGraph terminal** (Step 9) or the `curl` example under [Manual component checks](#manual-component-checks-optional) for the resume round-trip—then return to Jaeger (UI Step 6) to show both spans.

**Non-destructive contrast (optional):** call the tool with a script name that does **not** contain `drop` / `destructive` (e.g. `V001__init.sql`) and show an immediate **`resultType`: `"complete"`** with no pause.

---

### UI Step 5 — LLM playground: probe LM Studio via the gateway

Gateway `llm` targets LM Studio at `http://127.0.0.1:1234/v1`. The LangGraph agent still chats with LM Studio **directly**; this step is for console/demo proof that the gateway LLM path works.

1. In the admin UI, open **LLM** / **LLM playground** (agentgateway 1.3+).
2. Select model **`qwen/qwen3.6-35b-a3b`** (or whichever model LM Studio currently serves — keep it aligned with `.env` `MODEL_NAME` and `agentgateway.yaml` `llm.params.model`).
3. Optionally set a short system prompt (e.g. “You are a concise demo assistant.”).
4. Send a user message such as: `Reply with the single word: pong`.
5. Confirm a successful model reply and, if shown, latency / token metrics.

If the model list is empty: verify LM Studio is up, `OPENAI_API_KEY` is present in the agentgateway process environment, and re-validate the config (`--validate-only`).

---

### UI Step 6 — Optional: inspect traces in Jaeger after UI / terminal runs

Tracing is configured in `agentgateway.yaml` (`frontendPolicies.tracing` → `localhost:4317`, full sampling). The core HITL demo does **not** require Jaeger.

**Start Jaeger**

```bash
# Option A — harness (.env)
ENABLE_JAEGER=1
uv run python main.py

# Option B — manual
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
# or: docker start jaeger
```

**After** Tool Playground pause+resume and/or a full LangGraph HITL run:

1. Open **[http://localhost:16686](http://localhost:16686)**.
2. Find recent traces for gateway / MCP traffic.
3. Confirm **two** tool round-trips are distinguishable (initial `input_required` path and resume/`complete` path).

If Jaeger is down, the migration demo still succeeds; the UI will simply show no new spans.

---

### Suggested presenter order

| Order | Where | What you show |
| --- | --- | --- |
| 1 | Terminal | `uv run python main.py` — harness + TRACE/AGENT bands |
| 2 | Admin UI | Tool Playground → `apply_db_migration` → `input_required` |
| 3 | Terminal | HITL answers (`confirm_drop` / `environment_tag`) → `complete` |
| 4 | Admin UI | LLM playground → short LM Studio probe |
| 5 | Jaeger (optional) | Two MCP round-trips for pause + resume |

---

## What you just demonstrated

1. Destructive tool call → `resultType: input_required` + HMAC `requestState` (terminal agent and/or admin **Tool Playground**)
2. Socket closed; no sticky `Mcp-Session-Id`
3. Operator input in the terminal (or playground resume, if supported)
4. Retry via **agentgateway** → any-ready MCP instance can verify state and finish with `resultType: complete`
5. (Optional) Gateway **LLM playground** reaches LM Studio; Jaeger shows pause + resume spans

## Manual component checks (optional)

Use these if you want to inspect layers separately (stop `main.py` first to free ports):

```bash
# Terminal A — MCP server
export $(grep -v '^#' .env | xargs)   # or set MCP_HMAC_SECRET in the shell
uv run uvicorn mcp_server.server:app --host 127.0.0.1 --port 8000

# Terminal B — gateway
agentgateway -f agentgateway.yaml

# Terminal C — smoke tools/call (should return input_required)
curl -s http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  -H 'Mcp-Name: apply_db_migration' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"apply_db_migration","arguments":{"cluster_id":"prod-db-01","script_name":"V004__drop_legacy_users.sql"},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"curl","version":"0"},"io.modelcontextprotocol/clientCapabilities":{"elicitation":{}}}}}'
```

## Repository layout

```text
main.py                 # one-command harness (+ optional Jaeger)
agentgateway.yaml       # L7 proxy (stateless MCP + llm + OTLP tracing)
mcp_server/             # FastAPI MCP tool + HMAC crypto
agent/                  # LangGraph client + httpx MCP client
.env.example            # config template (incl. ENABLE_JAEGER)
specs/001-mrtr-db-migration/     # MRTR HITL Spec Kit artifacts
specs/002-gateway-llm-tracing/   # LLM playground + Jaeger Spec Kit artifacts
```

## Governing principles

Project rules live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md):

1. **Connection Statelessness** — no persistent SSE GET sockets; `Mcp-Session-Id` prohibited  
2. **Protocol Precision** — top-level `resultType`: `complete` \| `input_required`  
3. **HMAC Integrity** — HMAC-SHA256 continuation handles (`requestState`)  
4. **Infrastructure Integration** — tools via agentgateway `:8080`; LM Studio as above  
5. **Modular Verification** — separable MCP server, agentgateway, and LangGraph runloop  

More detail: [specs/001-mrtr-db-migration/quickstart.md](specs/001-mrtr-db-migration/quickstart.md) and [specs/002-gateway-llm-tracing/quickstart.md](specs/002-gateway-llm-tracing/quickstart.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Fail-fast: LLM unreachable | LM Studio server running on `:1234`; model loaded; `OPENAI_API_BASE` / `MODEL_NAME` match |
| `agentgateway` not found | Re-run install script; confirm `which agentgateway` |
| Port already in use | Stop other listeners on 8000/8080/1234 (also 15000/4317/16686 if using UI/Jaeger) |
| HMAC / invalid `requestState` | Same `MCP_HMAC_SECRET` for the whole process; answer within 5 minutes |
| Invalid environment tag | Exactly `dev`, `staging`, or `prod` (case-sensitive) |
| Gateway returns unexpected session behavior | `agentgateway.yaml` must keep `statefulMode: stateless` |
| HTTP 406 from gateway | Client must send `Accept: application/json, text/event-stream` |
| `_meta.protocolVersion is required` | Include MCP 2026-07-28 `_meta` keys under `params` (see contracts) |
| LLM playground empty / errors | `OPENAI_API_KEY` exported for agentgateway; LM Studio up; `llm.params.model` matches loaded model |
| No traces in Jaeger | Collector on `:4317`; `frontendPolicies.tracing` present; re-run a tool call; `ENABLE_JAEGER=1` or manual `docker start jaeger` |

## License

See [LICENSE](LICENSE).
