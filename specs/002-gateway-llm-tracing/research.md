# Research: Agentgateway LLM Playground & Trace Observability

**Feature**: `002-gateway-llm-tracing`  
**Date**: 2026-08-02

## 1. LLM provider shape for LM Studio

**Decision**: Add a root-level `llm.models` entry using `provider.custom` with `formats: [{ type: completions }]` and `params.baseUrl: http://127.0.0.1:1234/v1`, `params.model` matching `.env` `MODEL_NAME` (`qwen/qwen3.6-35b-a3b`), and `params.apiKey: $OPENAI_API_KEY` (agentgateway env expansion). Keep model match name `"*"` so any LM Studio-served id can be selected in the playground while defaulting `params.model` to the demo model.

**Rationale**: Agentgateway docs recommend `provider.custom` for OpenAI-compatible local hosts (LM Studio / vLLM) without a first-class provider page. `--validate-only` accepts this shape alongside the existing `mcp:` block. Env-based API key avoids committing secrets.

**Alternatives considered**:
- `provider: openAI` with host/port overrides — workable for some OpenAI-compatible hosts, but custom + `baseUrl` is the documented LM Studio path and validated cleanly.
- Wildcard-only without `params.model` — weaker default for playground probes; keep explicit default model.

## 2. Coexistence with existing MCP proxy config

**Decision**: Extend the current root `mcp:` config (port `8080`, `statefulMode: stateless`, `devops-migration` → `http://127.0.0.1:8000/mcp`, CORS for admin UI) by adding sibling `llm:` and `frontendPolicies:` keys. Do **not** migrate to `binds:` / multi-gateway layout in this feature.

**Rationale**: Validated with `agentgateway -f … --validate-only` (`Configuration is valid!`). Preserves the constitution tool path (`:8080`) and minimizes harness churn. Full `gateways:` rewrite is out of scope unless validate fails on a presenter’s binary version.

**Alternatives considered**:
- Migrate to `gateways.default` + shared UI/LLM/MCP — cleaner long-term, higher break risk for the working demo.
- Separate LLM-only process — unnecessary complexity for a local demo.

## 3. Admin UI / LLM playground verification

**Decision**: Document admin UI at `http://localhost:15000/ui/` (existing CORS allow-origin). Presenters verify models under the LLM / playground section and send a short chat probe. No custom UI work.

**Rationale**: Matches current demo CORS and agentgateway admin UI conventions. Spec scopes this feature to configuration + docs, not UI redesign.

**Alternatives considered**: Embedding a custom HTML playground — rejected (duplicates gateway UI).

## 4. Agent chat routing (LangGraph ↔ LLM)

**Decision**: Keep LangGraph on **direct** LM Studio (`OPENAI_API_BASE` / `MODEL_NAME`). Gateway `llm:` is for console/playground demos and screenshots only.

**Rationale**: Spec assumption and lowest friction for HITL reliability (FR-012 / US4). Routing chat through gateway would require base URL changes, extra failure modes, and more validation without improving the MRTR story.

**Alternatives considered**:
- Point `ChatOpenAI` at gateway LLM port — deferred; revisit only if playground + agent must share identical gen_ai spans in one trace.

## 5. OTLP / Jaeger tracing

**Decision**:
- Add `frontendPolicies.tracing` with `host: localhost:4317` and `randomSampling: true` (full demo sampling per agentgateway OpenTelemetry docs).
- Document Jaeger all-in-one:

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

- Viewer: `http://localhost:16686`
- Harness: optional `ENABLE_JAEGER=1` (or equivalent) attempts to start/reuse the container; if Docker/Jaeger unavailable, **warn and continue** (tracing optional; SC-006). Never fail the HITL story solely because Jaeger is down unless a future `REQUIRE_JAEGER` flag is set (out of scope for v1).

**Rationale**: Matches official agentgateway Jaeger / OTLP guidance. Full sampling maximizes screenshot success. Optional harness keeps “no Docker” presenters unblocked.

**Alternatives considered**:
- OpenTelemetry Collector + Jaeger compose — better for production; overkill for local demo.
- Prometheus-only — does not satisfy UI-style trace screenshots for pause/resume.

## 6. Environment and contracts

**Decision**:
- Extend `.env.example` with `ENABLE_JAEGER=0`, document ports `15000` (admin UI), `16686` (Jaeger UI), `4317` (OTLP gRPC), and remind that `MODEL_NAME` / `OPENAI_API_*` must stay aligned with `agentgateway.yaml` `llm.params`.
- Mirror the full gateway YAML under `specs/002-gateway-llm-tracing/contracts/agentgateway.yaml`.
- Point harness `CONTRACT_GATEWAY` fallback at the **002** contract (or copy-forward) so regenerated configs include LLM + tracing.
- Minor cleanup: drop CORS `exposeHeaders: [Mcp-Session-Id]` from the new contract (constitution forbids sticky sessions; header unused).

**Rationale**: FR-009–FR-011; keeps example env and contracts the source of truth for implement/tasks.

## 7. Constitution impact

**Decision**: No constitution amendments. Feature strengthens Principle IV (gateway + LM Studio visibility) and leaves Principles I–III / V unchanged.

**Rationale**: Tools still via `:8080` stateless MCP; HMAC/`resultType` untouched; modules remain separable (gateway YAML + optional Docker Jaeger + docs/harness wiring).
