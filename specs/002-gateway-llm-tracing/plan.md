# Implementation Plan: Agentgateway LLM Playground & Trace Observability

**Branch**: `002-gateway-llm-tracing` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-gateway-llm-tracing/spec.md`

**Note**: This plan was produced by `/speckit-plan`. Gateway YAML validated with `agentgateway --validate-only`; LLM/tracing shapes checked against agentgateway standalone docs (Context7 + official OpenTelemetry/Jaeger pages).

## Summary

Extend the existing MCP MRTR DevOps demo so **agentgateway** is demo-visible for LLM and observability: (1) add an `llm` provider binding to LM Studio so the admin UI LLM playground lists/uses the demo model; (2) enable `frontendPolicies.tracing` to OTLP `localhost:4317` with full sampling and document (optionally harness-start) Jaeger all-in-one for pause/resume MCP screenshots. Keep `devops-migration` + `statefulMode: stateless`, HMAC/`resultType` semantics, tools via `:8080`, and LangGraph chat **direct** to LM Studio. Update `.env.example`, README, contracts, and harness fallback paths.

## Technical Context

**Language/Version**: Python 3.11+ managed with `uv` (harness/docs only; no new runtime language)

**Primary Dependencies**: Existing stack (`langgraph`, `langchain-openai`, `httpx`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`) + **agentgateway** binary + optional **Docker** (`jaegertracing/all-in-one`)

**Storage**: N/A (Jaeger in-memory/ephemeral for local demo)

**Testing**: `pytest` — config contract checks (YAML presence / key fields); optional integration skip-if-unavailable for gateway validate and Jaeger reachability; existing MRTR contract tests must stay green

**Target Platform**: Local macOS/Linux presenter machine (LM Studio + agentgateway + optional Docker)

**Project Type**: Demo enhancement (gateway config + harness/docs) on existing multi-module repo

**Performance Goals**: LLM console model visibility &lt; 2 minutes (SC-001); trace findability &lt; 3 minutes after HITL (SC-003); ≤1 minute added wall time vs baseline excluding image pull (SC-005)

**Constraints**:
- MCP `2026-07-28` / SEP-2322 unchanged (`complete` \| `input_required`, HMAC `requestState`)
- `statefulMode: stateless`; no sticky MCP sessions
- Tools via agentgateway `:8080`; LM Studio `http://127.0.0.1:1234/v1`, model `qwen/qwen3.6-35b-a3b`
- Tracing optional for core HITL (no hard Jaeger dependency by default)
- Gateway config MUST pass `agentgateway -f agentgateway.yaml --validate-only`

**Scale/Scope**: Single-operator local demo; admin UI + Jaeger screenshots; no K8s / no OTel Collector compose

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Pre-research | Post-design |
| --- | --- | --- |
| Connection Statelessness | PASS — keep `statefulMode: stateless`; no session pinning | PASS — contract YAML drops unused `Mcp-Session-Id` exposeHeaders; mode unchanged |
| Protocol Precision | PASS — no MRTR payload changes | PASS — observability is sidecar to existing shapes |
| HMAC Integrity | PASS — untouched | PASS — crypto paths unchanged |
| Infrastructure Integration | PASS — tools `:8080`; LM Studio via gateway LLM + existing agent path | PASS — `llm` → LM Studio; tools still via gateway; agent chat remains direct LM Studio (documented) |
| Modular Verification | PASS — config/docs/harness separable from MCP server logic | PASS — contracts under `002`; Jaeger optional module |

No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/002-gateway-llm-tracing/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── agentgateway.yaml
│   ├── llm-playground.md
│   └── observability.md
└── tasks.md             # /speckit-tasks (not this command)
```

### Source Code (repository root — touch points)

```text
.env.example                 # ENABLE_JAEGER + port notes; MODEL_NAME sync reminder
agentgateway.yaml            # llm + frontendPolicies.tracing + existing mcp
main.py                      # optional Jaeger start/warn; CONTRACT_GATEWAY → 002 contract
README.md                    # LLM UI + Jaeger sections (link quickstart)
docker-compose.jaeger.yaml   # optional thin wrapper (if preferred over documented docker run)
specs/002-gateway-llm-tracing/contracts/…
tests/contract/              # gateway yaml / env example assertions (lightweight)
```

**Structure Decision**: Keep flat multi-module layout from `001`. This feature primarily mutates **gateway config + harness/docs**; no new Python package. Optional Jaeger is external Docker, not in-process.

## Complexity Tracking

> No constitution violations requiring justification.

## Phase 0 & Phase 1 Outputs

| Artifact | Path |
| --- | --- |
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

### Implementation notes (for `/speckit-tasks`)

1. Replace root `agentgateway.yaml` with content from `contracts/agentgateway.yaml` (validate-only).
2. Wire `main.py` `CONTRACT_GATEWAY` to `specs/002-gateway-llm-tracing/contracts/agentgateway.yaml`.
3. Add `ENABLE_JAEGER` handling: start/reuse `jaeger` container; warn on failure; never block HITL.
4. Export `OPENAI_API_KEY` into agentgateway process environment when spawning gateway.
5. Update README + `.env.example` from quickstart ports/verification.
6. Keep LangGraph `_build_llm()` on direct LM Studio.
7. Add lightweight contract test: required keys present in committed `agentgateway.yaml` / example env.
