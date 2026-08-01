# Implementation Plan: MRTR Database Migration HITL Demo

**Branch**: `001-mrtr-db-migration` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-mrtr-db-migration/spec.md`

**Note**: This plan was produced by `/speckit-plan`. Technical choices validated against Context7 (LangGraph, FastAPI, Pydantic) and MCP 2026-07-28 MRTR + agentgateway docs.

## Summary

Build an end-to-end, connection-stateless DevOps demo where a LangGraph agent calls `apply_db_migration` through **agentgateway** (`statefulMode: stateless`, port 8080). Destructive scripts return SEP-2322 `InputRequiredResult` (`resultType: "input_required"`) with form elicitation + HMAC-SHA256 `requestState`. The agent pauses via LangGraph `interrupt()`, collects terminal answers, retries with `inputResponses` + echoed `requestState`, and completes with `resultType: "complete"`. `main.py` automates MCP server + agentgateway startup, LM Studio connectivity validation, and the interactive runloop.

## Technical Context

**Language/Version**: Python 3.11+ managed with `uv`

**Primary Dependencies**: `langgraph`, `langchain-openai`, `httpx`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv` (plus stdlib `hmac`, `hashlib`, `base64`, `subprocess` for harness/crypto)

**Storage**: N/A for migration apply (simulated). LangGraph uses in-memory checkpointer (`MemorySaver`) for interrupt/resume within a demo session. Continuity across MCP round-trips is entirely in `requestState` (no server session store).

**Testing**: `pytest` with `tests/unit/` (crypto, allow-list, destructive detection), `tests/contract/` (MRTR JSON shapes / headers), `tests/integration/` (httpx against live MCP via gateway when harness deps available)

**Target Platform**: Local macOS/Linux developer machine (LM Studio + agentgateway binary + uv)

**Project Type**: Multi-module demo (MCP HTTP service + L7 proxy config + LangGraph CLI agent + orchestrator)

**Performance Goals**: Interactive demo; destructive happy-path under 5 minutes (SC-001). Tool round-trips should feel interactive (< a few seconds excluding LLM thinking time).

**Constraints**:
- MCP protocol version `2026-07-28`; SEP-2322 MRTR only (`complete` | `input_required`)
- No persistent SSE GET for HITL; no `Mcp-Session-Id`; agentgateway **must** use `statefulMode: stateless`
- HMAC-SHA256 integrity for `requestState`; 5-minute TTL; bind cluster + script
- Tool calls only via gateway `:8080`; LLM = LM Studio `http://127.0.0.1:1234/v1`, model `qwen/qwen3.6-35b-a3b`
- `environment_tag` ∈ `{dev, staging, prod}` from one maintainable allow-list constant
- Fail-fast LM connectivity check before HITL story

**Scale/Scope**: Single-operator local demo; one default scenario (`prod-db-01` / `V004__drop_legacy_users.sql`); mocked migration apply

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Pre-research | Post-design |
| --- | --- | --- |
| Connection Statelessness | PASS — design forbids sticky SSE / `Mcp-Session-Id`; gateway `statefulMode: stateless` | PASS — contracts + `agentgateway.yaml` encode stateless mode |
| Protocol Precision | PASS — only `complete` \| `input_required` | PASS — Pydantic/dataclass models + contract fixtures |
| HMAC Integrity | PASS — `mcp_server/crypto.py` mint/verify | PASS — data-model payload fields + reject paths |
| Infrastructure Integration | PASS — gateway 8080, LM Studio defaults from `.env` | PASS — quickstart + harness automation |
| Modular Verification | PASS — `mcp_server/`, `agent/`, `agentgateway.yaml`, `main.py` | PASS — structure below; independent test dirs |

No Complexity Tracking entries required (no justified violations).

## Project Structure

### Documentation (this feature)

```text
specs/001-mrtr-db-migration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── mrtr-tools-call.md
│   └── agentgateway.yaml
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
.env                         # local secrets/config (gitignored)
.env.example                 # committed template without secrets
pyproject.toml               # uv project + deps
agentgateway.yaml            # L7 MCP proxy (stateless) — also mirrored under contracts/
main.py                      # CLI orchestrator: validate LLM, start MCP + gateway, run agent
mcp_server/
  __init__.py
  mrtr_types.py              # SEP-2322 Pydantic models / dataclasses
  crypto.py                  # HMAC-SHA256 requestState mint + verify
  server.py                  # FastAPI POST /mcp — apply_db_migration
agent/
  __init__.py
  mcp_client.py              # httpx client: headers, MRTR parse/retry
  graph.py                   # LangGraph: tool call → human_input interrupt → retry
tests/
  unit/
  contract/
  integration/
```

**Structure Decision**: Flat multi-module layout at repo root (per feature request and constitution Principle V). Shared SEP-2322 types live in `mcp_server/mrtr_types.py` and are imported by `agent/` to avoid drift. Gateway config is a first-class file at repo root; harness regenerates/ensures it on startup.

## Complexity Tracking

> No constitution violations requiring justification.
