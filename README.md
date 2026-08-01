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
| API gateway / L7 | agentgateway — Streamable HTTP proxy on port **8080** |
| MCP protocol | MCP **2026-07-28** stateless core + SEP-2322 MRTR payloads |

Local defaults (see `.env`, not committed):

- `AGENTGATEWAY_PORT=8080`
- `MCP_SERVER_PORT=8000`
- `OPENAI_API_BASE=http://127.0.0.1:1234/v1`
- `MODEL_NAME=qwen/qwen3.6-35b-a3b`
- `MCP_HMAC_SECRET` — shared secret for signing/verifying `requestState`

## Governing principles

Project rules live in [`.specify/memory/constitution.md`](.specify/memory/constitution.md):

1. **Connection Statelessness** — no persistent SSE GET sockets; `Mcp-Session-Id` prohibited  
2. **Protocol Precision** — top-level `resultType`: `complete` \| `input_required`  
3. **HMAC Integrity** — encrypt/sign continuation handles with HMAC-SHA256  
4. **Infrastructure Integration** — tools via agentgateway `:8080`; LM Studio as above  
5. **Modular Verification** — separable MCP server, agentgateway, and LangGraph runloop  

## Architecture (logical)

```text
Cursor / Spec-Kit
        │
        ▼
LangGraph client (runloop)
        │  tools/call  (Streamable HTTP)
        ▼
agentgateway :8080
        │
        ▼
MCP server :8000  ──►  HMAC requestState  ◄──  operator HITL
        │
        ▼
LM Studio :1234  (qwen/qwen3.6-35b-a3b)
```

## Quick start

See [specs/001-mrtr-db-migration/quickstart.md](specs/001-mrtr-db-migration/quickstart.md).

```bash
cp .env.example .env   # set MCP_HMAC_SECRET; keep LM Studio defaults
uv sync
uv run python main.py  # validates LLM, starts MCP + agentgateway, runs HITL demo
```

Requires: Python 3.11+, `uv`, LM Studio with `qwen/qwen3.6-35b-a3b`, and `agentgateway` on `PATH`.

## License

See [LICENSE](LICENSE).
