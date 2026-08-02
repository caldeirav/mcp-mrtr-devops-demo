---
description: "Task list for agentgateway LLM playground and OTLP/Jaeger observability"
---

# Tasks: Agentgateway LLM Playground & Trace Observability

**Input**: Design documents from `/specs/002-gateway-llm-tracing/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec Kit defaults treat tests as optional. Lean contract tests are included where the plan and constitution Principle V require config/env verification—not a full TDD mandate. Manual UI checks (admin LLM playground, Jaeger) are Independent Tests, not automated browser tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **MCP MRTR demo**: root `agentgateway.yaml` + `main.py`, `.env.example`, `README.md`, `specs/002-gateway-llm-tracing/`, `tests/contract/`, existing `agent/` / `mcp_server/` unchanged unless noted

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align env templates and confirm contract artifacts are the source of truth

- [ ] T001 [P] Extend `.env.example` with `ENABLE_JAEGER=0`, comments for ports `15000` (admin UI), `16686` (Jaeger UI), `4317` (OTLP), and a note that `MODEL_NAME` / `OPENAI_API_*` must stay aligned with `agentgateway.yaml` `llm.params`
- [ ] T002 [P] Confirm committed contracts exist and are complete under `specs/002-gateway-llm-tracing/contracts/` (`agentgateway.yaml`, `llm-playground.md`, `observability.md`)—fix gaps only if validate-only or docs drift

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Harness + root gateway wiring so LLM and tracing config can be loaded safely before story work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Point `CONTRACT_GATEWAY` in `main.py` at `specs/002-gateway-llm-tracing/contracts/agentgateway.yaml` (replace `001-…` fallback path)
- [ ] T004 Ensure `start_agentgateway()` in `main.py` passes `OPENAI_API_KEY` (and other needed env) into the agentgateway subprocess environment so `$OPENAI_API_KEY` expands for `llm.params.apiKey`
- [ ] T005 Sync repo-root `agentgateway.yaml` from `specs/002-gateway-llm-tracing/contracts/agentgateway.yaml` and verify with `agentgateway -f agentgateway.yaml --validate-only` (export `OPENAI_API_KEY` for validation)
- [ ] T006 [P] Add lightweight contract test asserting required keys (`llm`, `frontendPolicies.tracing`, `mcp.statefulMode: stateless`, `devops-migration`) in root `agentgateway.yaml` in `tests/contract/test_gateway_llm_tracing_config.py`
- [ ] T007 [P] Add lightweight contract test that `.env.example` documents `ENABLE_JAEGER`, `OPENAI_API_BASE`, `MODEL_NAME` in `tests/contract/test_env_example_observability.py`

**Checkpoint**: Foundation ready — root config validates; harness can spawn gateway with LLM env; contract tests green

---

## Phase 3: User Story 1 - Browse Local Models in the Gateway Console (Priority: P1) 🎯 MVP

**Goal**: Admin UI LLM / playground shows LM Studio–backed models and accepts a short chat probe; MCP `devops-migration` remains stateless on `:8080`.

**Independent Test**: With LM Studio up and gateway started, open `http://localhost:15000/ui/`, open LLM playground, confirm demo model, send a short prompt, receive a reply; Tool Playground still lists `apply_db_migration`.

### Implementation for User Story 1

- [ ] T008 [US1] Ensure root `agentgateway.yaml` `llm` block matches `contracts/llm-playground.md` (`provider.custom`, `completions`, `baseUrl: http://127.0.0.1:1234/v1`, `model: qwen/qwen3.6-35b-a3b`, `apiKey: $OPENAI_API_KEY`, match `"*"`) while keeping `mcp` target `devops-migration` and `statefulMode: stateless`
- [ ] T009 [US1] Preserve/adjust CORS under `mcp.policies.cors` for `http://localhost:15000` in `agentgateway.yaml` (no sticky-session pinning; do not reintroduce `Mcp-Session-Id` exposeHeaders)
- [ ] T010 [P] [US1] Document LLM playground verification steps (UI URL, model check, probe prompt) in `README.md` (link or embed from `specs/002-gateway-llm-tracing/quickstart.md` §3)
- [ ] T011 [US1] Manually smoke-check: start LM Studio + `uv run python main.py` (or gateway alone), confirm LLM section lists/uses demo model; note any binary/UI quirks in `specs/002-gateway-llm-tracing/quickstart.md` if found

**Checkpoint**: US1 MVP — gateway console LLM playground works against LM Studio without breaking MCP tooling

---

## Phase 4: User Story 2 - Inspect HITL Round-Trips in a Trace Viewer (Priority: P1)

**Goal**: Gateway exports OTLP traces with full sampling; optional Jaeger shows pause + resume MCP tool activity; HITL semantics unchanged when Jaeger is absent.

**Independent Test**: Start Jaeger (`:4317`/`:16686`), run destructive HITL through gateway, open Jaeger UI within ~3 minutes and distinguish initial `input_required` tool call vs resume/`complete` call.

### Implementation for User Story 2

- [ ] T012 [US2] Ensure `frontendPolicies.tracing` (`host: localhost:4317`, `randomSampling: true`) is present in root `agentgateway.yaml` per `contracts/observability.md` and re-run `--validate-only`
- [ ] T013 [US2] Implement optional Jaeger lifecycle in `main.py`: when `ENABLE_JAEGER=1`, start or reuse Docker container `jaeger` (`jaegertracing/all-in-one`, ports `16686`/`4317`); on failure **warn and continue**; never fail HITL solely because Jaeger is down
- [ ] T014 [US2] Add teardown-friendly handling in `main.py` (do not force-remove a pre-existing user Jaeger container; optional stop only if harness created it—document choice in code comment)
- [ ] T015 [P] [US2] Document Jaeger docker run/start, UI URL, and pause/resume verification checklist in `README.md` (from `contracts/observability.md` / quickstart §4)
- [ ] T016 [US2] Manually smoke-check: `ENABLE_JAEGER=1` (or manual docker run) + destructive HITL; confirm two round-trips visible in `http://localhost:16686`; confirm `ENABLE_JAEGER=0` still completes HITL

**Checkpoint**: US2 — traces optional but demonstrable; core demo never hard-depends on Jaeger

---

## Phase 5: User Story 3 - Documented Demo Operator Path (Priority: P2)

**Goal**: First-time operators can enable LLM console + optional tracing from README/quickstart/env alone.

**Independent Test**: Dry-run the updated README/quickstart checklist; every port/flag mentioned exists in `.env.example` or contracts; no unpublished steps required for US1/US2.

### Implementation for User Story 3

- [ ] T017 [P] [US3] Expand `README.md` with a dedicated section covering LLM playground + Jaeger (ports cheat sheet, optional tracing, links to `specs/002-gateway-llm-tracing/quickstart.md`)
- [ ] T018 [P] [US3] Sync `specs/002-gateway-llm-tracing/quickstart.md` with any harness flag names / behaviors implemented in `main.py` (especially `ENABLE_JAEGER`)
- [ ] T019 [US3] Ensure `.env.example` and README agree on defaults (`ENABLE_JAEGER=0`) and that secrets guidance remains “never commit real `.env`”

**Checkpoint**: US3 — operator path is complete and consistent across docs/env/contracts

---

## Phase 6: User Story 4 - Agent Chat Path Remains Reliable (Priority: P3)

**Goal**: LangGraph stays on direct LM Studio; harness destructive happy path still works with new gateway config.

**Independent Test**: `uv run python main.py` completes destructive pause→approve→resume; `agent/graph.py` still uses `OPENAI_API_BASE` directly (not gateway LLM proxy).

### Implementation for User Story 4

- [ ] T020 [US4] Verify `agent/graph.py` `_build_llm()` still targets `OPENAI_API_BASE` / `MODEL_NAME` directly; add a short README note that gateway LLM is for admin playground, not agent chat
- [ ] T021 [US4] Run regression: `uv run pytest tests/ -q` and one interactive destructive harness path; fix any breakage from gateway YAML/CORS/env changes in `main.py` / `agentgateway.yaml` only as needed
- [ ] T022 [P] [US4] Add skip-friendly integration note or smoke assertion (if low-friction) that gateway config still routes MCP in `tests/integration/test_gateway_mrtr.py` without requiring Jaeger

**Checkpoint**: US4 — HITL demo reliability preserved alongside console LLM + optional traces

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency across contracts, root config, and docs

- [ ] T023 [P] Diff root `agentgateway.yaml` vs `specs/002-gateway-llm-tracing/contracts/agentgateway.yaml` and eliminate drift
- [ ] T024 [P] Update `.cursor/rules/specify-rules.mdc` only if plan/quickstart pointers or stack summary drifted during implement
- [ ] T025 Run full checklist from `specs/002-gateway-llm-tracing/quickstart.md` (LLM probe + optional Jaeger + harness HITL) and fix any doc/code mismatches found
- [ ] T026 [P] Confirm `uv run pytest tests/ -q` passes (including new contract tests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP
- **US2 (Phase 4)**: After Foundational; ideally after US1 so gateway already has validated `llm` + mcp base (same YAML file—serialize US1→US2 on `agentgateway.yaml`)
- **US3 (Phase 5)**: After US1+US2 behaviors exist so docs match reality (can draft docs in parallel earlier, finalize after)
- **US4 (Phase 6)**: After Foundational; final regression after US1+US2 config lands
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
| --- | --- | --- |
| US1 (P1) | Phase 2 | MVP; edits `agentgateway.yaml` `llm` |
| US2 (P1) | Phase 2; serialize after US1 for same YAML | Jaeger harness + tracing keys |
| US3 (P2) | US1+US2 for accurate docs | Mostly README/quickstart/env |
| US4 (P3) | Phase 2 + post-US1/US2 config | Regression / agent path confirmation |

### Parallel Opportunities

- T001 ∥ T002 (Setup)
- T006 ∥ T007 (Foundational tests; after T005 preferred for green CI)
- T010 docs ∥ T008/T009 config (careful coordination)
- T015 docs ∥ T013/T014 harness (after T012)
- T017 ∥ T018 (US3 docs)
- T023 ∥ T024 ∥ T026 (Polish)

### Within Each User Story

- Config/harness before manual smoke
- Docs can trail implementation slightly but must match before story checkpoint
- US4 regression after YAML changes

---

## Parallel Example: User Story 1

```bash
# After Phase 2:
Task: "T008 [US1] Ensure llm block in agentgateway.yaml"
Task: "T010 [P] [US1] Document LLM playground in README.md"  # parallel doc

# Then sequential smoke:
Task: "T011 [US1] Manual smoke-check admin UI LLM playground"
```

## Parallel Example: User Story 2

```bash
Task: "T012 [US2] Ensure frontendPolicies.tracing in agentgateway.yaml"
# Then:
Task: "T013 [US2] ENABLE_JAEGER lifecycle in main.py"
Task: "T015 [P] [US2] Document Jaeger in README.md"  # parallel with T013/T014
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2
2. Complete Phase 3 (US1) — LLM playground visible
3. **STOP and VALIDATE** admin UI model list + probe
4. Demo/screenshot ready even without Jaeger

### Incremental Delivery

1. Setup + Foundational → validated gateway + harness env
2. US1 → LLM console MVP
3. US2 → Jaeger traces for HITL screenshots
4. US3 → polished operator docs
5. US4 → regression confidence
6. Polish → zero drift

### Suggested MVP Scope

**US1 only** (Phases 1–3): gateway LLM playground against LM Studio.

---

## Notes

- Do not route LangGraph chat through gateway LLM in this feature
- Do not hard-fail harness when Jaeger/Docker is missing
- Keep `statefulMode: stateless`; no `Mcp-Session-Id` pinning
- Commit after each task or logical group; stop at checkpoints to validate
- Format: every task uses `- [ ] Tnnn …` with file paths; story tasks include `[USn]`
