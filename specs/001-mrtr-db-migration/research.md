# Research: MRTR Database Migration HITL Demo

**Date**: 2026-08-01  
**Sources**: Context7 (`/langchain-ai/langgraph`, `/websites/fastapi_tiangolo`, `/pydantic/pydantic`), [MCP MRTR 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr), [agentgateway Streamable HTTP](https://agentgateway.dev/docs/standalone/latest/mcp/connect/http/)

## 1. Protocol: SEP-2322 MRTR shapes

**Decision**: Implement official MCP 2026-07-28 MRTR types:
- `InputRequiredResult`: `{ "resultType": "input_required", "inputRequests": {...}, "requestState": "<opaque>" }`
- Complete tool results: `{ "resultType": "complete", ...tool fields... }`
- Retry `tools/call` with params including original arguments plus `inputResponses` (map keyed like `inputRequests`) and echoed `requestState`
- JSON-RPC `id` MUST differ between initial call and retry
- Clients MUST NOT parse `requestState`

**Rationale**: Matches published SEP-2322; constitution requires top-level `resultType` only `complete` | `input_required`.

**Alternatives considered**:
- Legacy server-initiated elicitation over sticky SSE — rejected (pre-2026, constitution Principle I)
- Custom top-level status enums (`rejected`, `cancelled`) — rejected (clarification: denial uses `complete` + messaging)

## 2. Elicitation form for confirm_drop / environment_tag

**Decision**: Single `inputRequests` entry (key e.g. `confirm_drop_form`) with `method: "elicitation/create"`, `params.mode: "form"`, schema properties `confirm_drop` (boolean) and `environment_tag` (string with enum/allow-list). Client maps terminal answers into:

```json
{
  "confirm_drop_form": {
    "action": "accept",
    "content": { "confirm_drop": true, "environment_tag": "prod" }
  }
}
```

**Rationale**: Official MRTR examples use elicitation form mode; keeps allow-list validation server-side on resume.

**Alternatives considered**: Ad-hoc flat `inputResponses` without elicitation envelope — simpler but less SEP-aligned.

## 3. requestState crypto

**Decision**: Opaque token = `base64url(payload_json) + "." + hex(HMAC-SHA256(secret, payload_b64))` where payload includes `cluster_id`, `script_name`, `iat` (unix ts), `method`, `tool`. Verify signature (constant-time), TTL ≤ 300s, and cluster/script bind on resume. Secret from `MCP_HMAC_SECRET`.

**Rationale**: Spec FR-004 + constitution Principle III (HMAC-SHA256, tamper detection). Base64url transport-safe. "Encrypt" intent from constitution satisfied for demo by not exposing mutable unsigned state; optional upgrade to Fernet/AEAD documented if secrets-in-payload expand.

**Alternatives considered**:
- Fernet (AES + HMAC) — stronger confidentiality; deferred unless payload grows sensitive
- Server-side session store — rejected (defeats MRTR demo)

## 4. Transport & headers

**Decision**: FastAPI app exposes `POST /mcp` (Streamable HTTP style JSON-RPC). Demo client sends:
- `Mcp-Protocol-Version: 2026-07-28`
- `Content-Type: application/json`
- Body: JSON-RPC `tools/call` with `params.name = "apply_db_migration"`
- Optional demo routing headers `Mcp-Method` / `Mcp-Name` validated when present (per original system requirements)

Never set or require `Mcp-Session-Id`.

**Rationale**: Aligns with user system requirements + constitution. Full MCP SDK FastMCP MRTR support may lag; thin FastAPI surface is controllable for the demo.

**Alternatives considered**: Depend solely on upstream MCP Python SDK MRTR — risk of incomplete SEP-2322 support for teaching demo.

## 5. agentgateway automation

**Decision**:
- Commit/generate `agentgateway.yaml` with:

```yaml
mcp:
  port: 8080
  statefulMode: stateless
  targets:
  - name: devops-migration
    mcp:
      host: http://127.0.0.1:8000/mcp
```

- `main.py` ensures file exists, locates `agentgateway` on `PATH`, starts `agentgateway -f agentgateway.yaml`, waits for port 8080, tears down on exit.
- If binary missing: clear install error pointing to agentgateway binary docs (fail fast, do not silently bypass gateway).

**Rationale**: Official docs document `statefulMode: stateless` which avoids `Mcp-Session-Id` — required by constitution. Port 8080 matches Principle IV.

**Alternatives considered**:
- Default stateful gateway + ignore session header — rejected (constitution)
- Direct client→MCP:8000 in demo path — rejected (Principle IV)

## 6. LangGraph HITL

**Decision**: Custom `StateGraph` with nodes roughly: `call_model` → `call_tool` → (conditional) `human_input` → `retry_tool` → end. On `resultType == "input_required"`, `human_input` uses LangGraph `interrupt(payload)` to surface elicitation schema; runner collects terminal input and resumes with `Command(resume=answers)`. Graph compiled with `MemorySaver` checkpointer + `thread_id` for the demo session.

**Rationale**: Context7 LangGraph docs confirm `interrupt()` + `Command(resume=...)` as the supported HITL primitive; node re-executes from start on resume—keep side effects idempotent / store pending MRTR fields in graph state before interrupt.

**Alternatives considered**:
- `interrupt_before=["tools"]` on prebuilt react agent — less control over MRTR retry payload
- Blocking `input()` inside tool node without interrupt — works for CLI but weaker LangGraph story

## 7. LLM client

**Decision**: `langchain_openai.ChatOpenAI` with `base_url`/`api_key`/`model` from `.env` (`OPENAI_API_BASE`, `OPENAI_API_KEY`, `MODEL_NAME`). Harness probes `GET {base}/models` or a tiny chat completion before starting the HITL story (FR-014).

**Rationale**: LM Studio OpenAI-compatible API; constitution model pin.

## 8. Packaging with uv

**Decision**: `uv init` / `pyproject.toml` with Python `>=3.11`, deps listed in Technical Context; `uv sync` + `uv run python main.py` as canonical entry.

**Rationale**: User-requested runtime toolchain.

## 9. Denial vs protocol error

**Decision** (from clarifications): Valid HMAC + declined/invalid allow-list → `resultType: "complete"` with denied/cancelled text (not applied). Invalid/expired/tampered `requestState` → JSON-RPC error (fail closed).

**Rationale**: Spec clarifications session 2026-08-01.

## Resolved unknowns

All Technical Context items were supplied by user input + constitution; no remaining `NEEDS CLARIFICATION` blockers for planning.
