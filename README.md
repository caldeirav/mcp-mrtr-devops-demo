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
```

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
2. Ensures `agentgateway.yaml` exists (`statefulMode: stateless`, `:8080` → MCP `:8000/mcp`)
3. Starts the MCP server on `MCP_SERVER_PORT` (default **8000**)
4. Starts `agentgateway -f agentgateway.yaml` on **8080** (logs redirected to `.demo_logs/`)
5. Runs the LangGraph agent for defaults **`prod-db-01`** / **`V004__drop_legacy_users.sql`**
6. On Ctrl+C / exit, stops child processes

Terminal output is banded so you can tell layers apart:

| Band | Meaning |
| --- | --- |
| `TRACE` | Harness / LangGraph / HTTP execution |
| `AGENT` | LLM narrative and packaged answers |
| `HITL` | Your operator prompts (no open SSE socket) |
| `SEP` | Detailed request/response + ★ what changed in 2026-07-28 / SEP-2322 |

`SEP` panels highlight new fields (`resultType`, `requestState`, `inputRequests` / `inputResponses`, per-request `_meta`, `Mcp-Method` / `Mcp-Name`) and call out removed sticky-session behavior (`Mcp-Session-Id` absent). Set `NO_COLOR=1` to disable ANSI colors.

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

## What you just demonstrated

1. Destructive tool call → `resultType: input_required` + HMAC `requestState`
2. Socket closed; no sticky `Mcp-Session-Id`
3. Operator input in the terminal
4. Retry via **agentgateway** → any-ready MCP instance can verify state and finish with `resultType: complete`

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
main.py                 # one-command harness
agentgateway.yaml       # L7 proxy (stateless)
mcp_server/             # FastAPI MCP tool + HMAC crypto
agent/                  # LangGraph client + httpx MCP client
.env.example            # config template
specs/001-mrtr-db-migration/   # Spec Kit artifacts (spec, plan, tasks, contracts)
```

## Governing principles

Project rules live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md):

1. **Connection Statelessness** — no persistent SSE GET sockets; `Mcp-Session-Id` prohibited  
2. **Protocol Precision** — top-level `resultType`: `complete` \| `input_required`  
3. **HMAC Integrity** — HMAC-SHA256 continuation handles (`requestState`)  
4. **Infrastructure Integration** — tools via agentgateway `:8080`; LM Studio as above  
5. **Modular Verification** — separable MCP server, agentgateway, and LangGraph runloop  

More detail: [specs/001-mrtr-db-migration/quickstart.md](specs/001-mrtr-db-migration/quickstart.md).

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Fail-fast: LLM unreachable | LM Studio server running on `:1234`; model loaded; `OPENAI_API_BASE` / `MODEL_NAME` match |
| `agentgateway` not found | Re-run install script; confirm `which agentgateway` |
| Port already in use | Stop other listeners on 8000/8080/1234 |
| HMAC / invalid `requestState` | Same `MCP_HMAC_SECRET` for the whole process; answer within 5 minutes |
| Invalid environment tag | Exactly `dev`, `staging`, or `prod` (case-sensitive) |
| Gateway returns unexpected session behavior | `agentgateway.yaml` must keep `statefulMode: stateless` |
| HTTP 406 from gateway | Client must send `Accept: application/json, text/event-stream` |
| `_meta.protocolVersion is required` | Include MCP 2026-07-28 `_meta` keys under `params` (see contracts) |

## License

See [LICENSE](LICENSE).
