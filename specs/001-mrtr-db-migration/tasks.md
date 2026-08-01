---
description: "Task list for MRTR database migration HITL demo"
---

# Tasks: MRTR Database Migration HITL Demo

**Input**: Design documents from `/specs/001-mrtr-db-migration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Optional per Spec Kit defaults. Lean unit/contract tasks are included where the constitution requires modular verification (HMAC, MRTR shapes, allow-list)—not a full TDD mandate.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **MCP MRTR demo**: `mcp_server/`, `agent/`, root `agentgateway.yaml` + `main.py`, `tests/{unit,contract,integration}/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: uv project, package layout, env templates, gateway config stub

- [ ] T001 Create package directories and `__init__.py` files for `mcp_server/` and `agent/` plus `tests/unit/`, `tests/contract/`, `tests/integration/` per plan.md
- [ ] T002 Initialize uv Python 3.11+ project in `pyproject.toml` with dependencies `langgraph`, `langchain-openai`, `httpx`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, and dev dep `pytest`
- [ ] T003 [P] Add committed `.env.example` (no secrets) documenting `OPENAI_API_BASE`, `OPENAI_API_KEY`, `MODEL_NAME`, `AGENTGATEWAY_PORT`, `MCP_SERVER_PORT`, `MCP_HMAC_SECRET`
- [ ] T004 [P] Copy `specs/001-mrtr-db-migration/contracts/agentgateway.yaml` to repo-root `agentgateway.yaml` (`statefulMode: stateless`, port 8080 → `http://127.0.0.1:8000/mcp`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared SEP-2322 types, HMAC crypto, constants, FastAPI app skeleton—required before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement canonical constants (`ENVIRONMENT_TAGS`, TTL 300s, destructive keywords, defaults, protocol/tool names) in `mcp_server/mrtr_types.py`
- [ ] T006 [P] Implement SEP-2322 Pydantic models (`InputRequiredResult`, `InputRequests`/`ElicitRequest`, `InputResponses`/`ElicitResult`, `CompleteResult`, `ApplyDbMigrationArgs`, `RequestStatePayload`) in `mcp_server/mrtr_types.py` per data-model.md
- [ ] T007 [P] Implement HMAC-SHA256 mint/verify for `requestState` (`base64url(payload).hmac_hex`, TTL + bind checks) in `mcp_server/crypto.py`
- [ ] T008 Create FastAPI app skeleton with `POST /mcp` JSON-RPC router stub (header checks for `Mcp-Protocol-Version: 2026-07-28`; reject/ignore `Mcp-Session-Id`) in `mcp_server/server.py`
- [ ] T009 [P] Add unit tests for crypto mint/verify/tamper/expiry in `tests/unit/test_crypto.py`
- [ ] T010 [P] Add unit tests for allow-list constant and destructive keyword helper in `tests/unit/test_constants.py`

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 - Authorize a Destructive Migration (Priority: P1) 🎯 MVP

**Goal**: Destructive script yields `input_required` with elicitation + HMAC `requestState`; agent pauses for terminal input and retries to `complete` (applied) via gateway.

**Independent Test**: Call `apply_db_migration` for `prod-db-01` / `V004__drop_legacy_users.sql` through gateway; confirm pause; enter `confirm_drop=true` and `environment_tag=prod`; receive simulated apply `complete` without restarting the agent session.

### Implementation for User Story 1

- [ ] T011 [US1] Implement destructive detection + `InputRequiredResult` response (elicitation key `confirm_drop_form`, schema for `confirm_drop` + `environment_tag` enum) in `mcp_server/server.py`
- [ ] T012 [US1] Implement resume path: verify `requestState`, accept valid `inputResponses`, return `resultType: complete` applied summary (simulated) in `mcp_server/server.py`
- [ ] T013 [P] [US1] Implement httpx MCP client (protocol headers, JSON-RPC ids, parse `resultType`, echo `requestState`, build `inputResponses`) targeting gateway base URL in `agent/mcp_client.py`
- [ ] T014 [US1] Implement LangGraph state graph (`call_tool` → `human_input` with `interrupt()` → `retry_tool`) and `MemorySaver` thread config in `agent/graph.py`
- [ ] T015 [US1] Wire terminal prompts for `confirm_drop` and `environment_tag` and resume via `Command(resume=...)` in `agent/graph.py` (or small helper colocated there)
- [ ] T016 [P] [US1] Add contract fixture/assertions for initial `input_required` shape from `contracts/mrtr-tools-call.md` in `tests/contract/test_mrtr_input_required.py`

**Checkpoint**: US1 happy-path MRTR authorization works (MCP + agent; harness may still be manual process start)

---

## Phase 4: User Story 2 - Reject or Fail Closed on Invalid Continuation (Priority: P2)

**Goal**: Tampered/expired/mismatched `requestState` fails closed (JSON-RPC error); declined confirm or invalid allow-list tag returns `complete` with denied/cancelled summary (not applied).

**Independent Test**: Replay retry with modified `requestState` → error, no apply; retry with `confirm_drop=false` or `environment_tag=qa` → `complete` denied text, no apply.

### Implementation for User Story 2

- [ ] T017 [US2] Implement fail-closed JSON-RPC errors for invalid/expired/tampered/bind-mismatched `requestState` in `mcp_server/server.py` and `mcp_server/crypto.py` as needed
- [ ] T018 [US2] Implement denied/cancelled `CompleteResult` when `confirm_drop` is false, answers missing, or `environment_tag` ∉ `{dev, staging, prod}` in `mcp_server/server.py`
- [ ] T019 [P] [US2] Add unit/contract tests for tamper, expiry, and deny paths in `tests/unit/test_resume_reject.py` and/or `tests/contract/test_mrtr_deny.py`
- [ ] T020 [US2] Ensure agent surfaces denial/error messages clearly in terminal after retry in `agent/graph.py`

**Checkpoint**: US1 + US2 integrity and soft-deny behaviors are verifiable without the full harness

---

## Phase 5: User Story 3 - Non-Destructive Migration Completes Without Pause (Priority: P3)

**Goal**: Script names without destructive keywords return `complete` immediately with no elicitation.

**Independent Test**: Call tool with e.g. `V001__add_index.sql` → `resultType: complete`, no human_input interrupt.

### Implementation for User Story 3

- [ ] T021 [US3] Implement non-destructive immediate `CompleteResult` path (no `inputRequests`) in `mcp_server/server.py`
- [ ] T022 [P] [US3] Add contract/unit coverage for non-destructive completion in `tests/contract/test_mrtr_non_destructive.py`
- [ ] T023 [US3] Ensure agent graph skips `human_input` when initial tool result is `complete` in `agent/graph.py`

**Checkpoint**: Conditional HITL is demonstrated (pause only when destructive)

---

## Phase 6: User Story 4 - One-Command End-to-End Demo (Priority: P2)

**Goal**: `main.py` validates LM Studio, starts MCP + agentgateway, runs default destructive scenario, supports HITL, tears down cleanly.

**Independent Test**: `uv run python main.py` alone completes US1 story (or fails fast with clear LLM/gateway errors); no manual subprocess orchestration.

### Implementation for User Story 4

- [ ] T024 [US4] Implement LM Studio reachability probe (fail-fast clear terminal error) before HITL story in `main.py`
- [ ] T025 [US4] Implement subprocess lifecycle: ensure `agentgateway.yaml`, start uvicorn `mcp_server.server:app` on `MCP_SERVER_PORT`, start `agentgateway -f agentgateway.yaml`, wait for ports, cleanup on exit in `main.py`
- [ ] T026 [US4] Trigger LangGraph run with defaults `prod-db-01` / `V004__drop_legacy_users.sql` via gateway URL from env in `main.py`
- [ ] T027 [US4] Load dotenv / env validation (required secrets and ports) in `main.py`
- [ ] T028 [P] [US4] Document run steps aligning with implementation in `specs/001-mrtr-db-migration/quickstart.md` and briefly link from `README.md`

**Checkpoint**: Presenter one-command demo path is complete

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, docs consistency, modular verification

- [ ] T029 [P] Add integration smoke test (skip if gateway/LLM unavailable) calling through `http://127.0.0.1:8080` in `tests/integration/test_gateway_mrtr.py`
- [ ] T030 [P] Verify no code path sets or requires `Mcp-Session-Id`; grep/guard in `mcp_server/server.py` and `agent/mcp_client.py`
- [ ] T031 Confirm `ENVIRONMENT_TAGS` is the single allow-list source used by server validation and elicitation schema in `mcp_server/mrtr_types.py` / `mcp_server/server.py`
- [ ] T032 Run `uv run pytest` and fix failures; validate quickstart commands manually against SC-001–SC-009 where environment allows

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Foundational — **MVP**
- **US2 (Phase 4)**: Depends on Foundational + US1 server resume path (T012)
- **US3 (Phase 5)**: Depends on Foundational + US1 tool routing; can proceed after T011 exists
- **US4 (Phase 6)**: Depends on US1 agent+server happy path (T014–T015); benefits from US2/US3 but not strictly blocked
- **Polish (Phase 7)**: Depends on desired stories being complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependency on other stories
- **US2 (P2)**: Extends US1 resume handling
- **US3 (P3)**: Independent branch on script-name detection after T011
- **US4 (P2)**: Orchestrates US1 (and demonstrates US2/US3 if already done)

### Parallel Opportunities

- T003/T004 after T001
- T006/T007 after T005; T009/T010 after T007/T005
- T013 parallel with T011–T012 once types/crypto exist
- T016, T019, T022, T028, T029, T030 marked [P]

### Within Each User Story

- Server behavior before or alongside client
- Client/graph before harness (US4)
- Contract checks can follow implementation closely

---

## Parallel Example: User Story 1

```bash
# After T005–T008:
Task: "Implement httpx MCP client in agent/mcp_client.py"
Task: "Implement destructive InputRequiredResult in mcp_server/server.py"

# After server input_required exists:
Task: "Add contract tests in tests/contract/test_mrtr_input_required.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup  
2. Complete Phase 2: Foundational  
3. Complete Phase 3: US1 (manual uvicorn + agentgateway OK)  
4. **STOP and VALIDATE** independent test for destructive HITL  
5. Then US2 → US3 → US4 harness polish  

### Incremental Delivery

1. Setup + Foundational → shared protocol core  
2. US1 → demo-able MRTR pause/resume  
3. US2 → integrity/deny story  
4. US3 → non-destructive contrast  
5. US4 → one-command presenter path  
6. Polish → pytest + constitution guards  

### Parallel Team Strategy

- Dev A: `mcp_server/` (T005–T012, T017–T018, T021)  
- Dev B: `agent/` (T013–T015, T020, T023)  
- Dev C: `main.py` + gateway automation (T024–T027) after US1 client exists  

---

## Notes

- [P] = different files, no incomplete-task dependencies  
- [USn] maps to spec user stories  
- Default demo identity: `prod-db-01` / `V004__drop_legacy_users.sql`  
- Gateway must remain `statefulMode: stateless`  
- Commit after each task or logical group  
- Suggested MVP = Phase 1–3 only  
