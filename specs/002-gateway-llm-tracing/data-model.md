# Data Model: Agentgateway LLM Playground & Trace Observability

**Feature**: `002-gateway-llm-tracing`  
**Date**: 2026-08-02

This feature is primarily configuration and operator-guide oriented. Entities below describe configuration records and runtime verification artifacts—not a persistent application database.

## Entities

### LLM Provider Binding

Association between the gateway console LLM section and the local LM Studio host.

| Field | Type | Rules |
| --- | --- | --- |
| `match_name` | string | `"*"` (accept any model id from playground) |
| `provider_kind` | enum | `custom` |
| `formats` | list | MUST include `completions` |
| `base_url` | URL | MUST be `http://127.0.0.1:1234/v1` unless overridden for local experiments |
| `default_model` | string | MUST match `.env` `MODEL_NAME` (constitution default `qwen/qwen3.6-35b-a3b`) |
| `api_key_ref` | env ref | `$OPENAI_API_KEY` (placeholder `lm-studio` for local) |

**Relationships**: Used by Admin UI LLM playground; independent of LangGraph chat path (direct LM Studio).

### MCP Target Binding (unchanged semantics)

| Field | Type | Rules |
| --- | --- | --- |
| `name` | string | `devops-migration` |
| `upstream` | URL | `http://127.0.0.1:8000/mcp` |
| `stateful_mode` | enum | MUST be `stateless` |
| `listen_port` | int | MUST be `8080` (or `AGENTGATEWAY_PORT`) |

**Relationships**: Agent tool calls → gateway → MCP server. Tracing observes these calls.

### Trace Export Policy

| Field | Type | Rules |
| --- | --- | --- |
| `otlp_host` | host:port | `localhost:4317` |
| `sampling` | bool/ratio | `true` (full sampling) for demos |
| `enabled_in_config` | bool | Always present in demo YAML; effectiveness depends on collector up |

### Trace Viewer Session

| Field | Type | Rules |
| --- | --- | --- |
| `ui_url` | URL | `http://localhost:16686` |
| `collector` | container/process | Jaeger all-in-one (or compatible OTLP receiver) |
| `expected_spans` | conceptual | At least two MCP tool round-trips for destructive HITL (input_required + resume) |

### Demo Operator Flags

| Field | Type | Rules |
| --- | --- | --- |
| `ENABLE_JAEGER` | bool string | Default `0`; `1` asks harness to start/reuse Jaeger container |
| `OPENAI_API_BASE` / `OPENAI_API_KEY` / `MODEL_NAME` | env | Existing; MUST stay consistent with LLM Provider Binding |

## State Transitions

### Tracing availability (operator view)

```text
[tracing optional / Jaeger down]
        │
        │ ENABLE_JAEGER=1 + Docker OK
        ▼
[collector listening :4317]
        │
        │ gateway exports spans (randomSampling true)
        ▼
[spans visible in viewer :16686]
```

HITL migration state machine (complete / input_required / resume) is unchanged from `001-mrtr-db-migration`.

## Validation Rules

1. Gateway config MUST validate with `agentgateway -f agentgateway.yaml --validate-only`.
2. `statefulMode` MUST remain `stateless`.
3. `MODEL_NAME` in `.env` SHOULD equal `llm.models[].params.model`.
4. Tracing MUST NOT be a hard dependency of the harness unless explicitly required later.
5. No sticky session headers introduced for MCP continuity.
