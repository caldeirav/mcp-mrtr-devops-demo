# Feature Specification: MRTR Database Migration HITL Demo

**Feature Branch**: `001-mrtr-db-migration`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Design an end-to-end demonstration of a DevOps AI Agent that utilizes Multi Round-Trip Requests (MRTR) under MCP SEP-2322 to perform human-in-the-loop database migration authorization. Includes a migration tool that yields for confirmation on destructive scripts, an agent that pauses for terminal operator input and retries with continuation state, and a complete harness that runs the server, gateway proxy, and agent end-to-end."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authorize a Destructive Migration (Priority: P1)

A DevOps operator asks the AI agent to apply a database migration whose script name indicates a destructive operation (for example, a script that drops legacy tables) against a named production cluster. The system detects the destructive intent, pauses for human authorization without keeping a live waiting connection, collects confirmation in the terminal, then completes the migration after valid approval.

**Why this priority**: This is the core demo value—stateless human-in-the-loop authorization for dangerous production changes.

**Independent Test**: Run the end-to-end harness with a destructive script name; verify the operator is prompted, can approve, and receives a successful completion outcome without restarting the agent from scratch.

**Acceptance Scenarios**:

1. **Given** the demo harness is running and the operator requests applying a migration whose script name contains destructive indicators (e.g. "drop"), **When** the agent invokes the migration capability for a target cluster, **Then** the system returns an input-required outcome asking for `confirm_drop` (boolean) and `environment_tag` (string), and does not leave a long-lived waiting connection open.
2. **Given** an input-required pause with a valid continuation handle, **When** the operator supplies affirmative confirmation and an environment tag in the terminal, **Then** the agent resubmits the same migration request with those answers and the continuation handle, and the system returns a complete outcome indicating the migration finished.
3. **Given** a successful complete outcome, **When** the operator reviews the terminal session, **Then** they can see that authorization and completion occurred in one continuous agent session (no full manual restart after the pause).

---

### User Story 2 - Reject or Fail Closed on Invalid Continuation (Priority: P2)

A DevOps operator (or a faulty client) attempts to continue a paused migration with a tampered, missing, or otherwise invalid continuation handle, or without required confirmation answers. The system refuses to apply the migration.

**Why this priority**: Integrity of the pause/resume token is essential to trust a stateless HITL design in production-like demos.

**Independent Test**: Replay a continuation with a modified continuation handle or missing confirmation fields and observe a clear failure without applying the migration.

**Acceptance Scenarios**:

1. **Given** a previously issued continuation handle, **When** a retry is sent with a tampered handle, **Then** the system rejects the request and does not report migration completion.
2. **Given** an input-required pause, **When** the operator declines confirmation (`confirm_drop` is false) or omits required answers, **Then** the system does not complete the destructive migration as successful.

---

### User Story 3 - Non-Destructive Migration Completes Without Pause (Priority: P3)

An operator requests a migration whose script name does not indicate destructive operations. The system applies the migration path without eliciting drop confirmation.

**Why this priority**: Shows that HITL pause is conditional, not forced on every migration—important for demo clarity and operator trust.

**Independent Test**: Run the agent against a non-destructive script name and verify completion without a human-input pause for drop confirmation.

**Acceptance Scenarios**:

1. **Given** a migration script name with no destructive indicators, **When** the agent requests application on a cluster, **Then** the system returns a complete outcome without asking for `confirm_drop` / `environment_tag`.

---

### User Story 4 - One-Command End-to-End Demo (Priority: P2)

A presenter starts a single harness entrypoint that brings up the migration service, the routing proxy, and the agent, then drives the HITL interaction through to completion for a destructive migration scenario.

**Why this priority**: The demo must be runnable as a coherent story, not a set of manually wired processes.

**Independent Test**: Start only the harness entrypoint with configured environment settings; complete User Story 1 without manually starting subordinate services outside the harness.

**Acceptance Scenarios**:

1. **Given** valid local environment configuration (model endpoint, gateway port, shared continuation secret), **When** the presenter launches the harness, **Then** the migration service and gateway proxy become available and the agent begins the migration scenario.
2. **Given** the harness is running, **When** the destructive migration HITL flow completes, **Then** the presenter has demonstrated pause, operator input, resume, and completion in one session.

### Edge Cases

- Script name matching is case-insensitive for destructive indicators such as "drop" or "destructive".
- Empty or missing `cluster_id` or `script_name` is rejected before any pause or completion.
- Continuation handle that is well-formed but expired or bound to different script/cluster details is rejected.
- Operator cancels or provides empty `environment_tag` when confirmation is requested—system does not treat the migration as successfully completed.
- Gateway or service restart between pause and resume: a valid continuation handle still allows completion on a fresh instance (no session stickiness required).
- Concurrent unrelated migration requests do not share or confuse continuation handles.

## Requirements *(mandatory)*

### Functional Requirements

<!--
  Constitution alignment (MCP MRTR): connection-stateless transport (no
  Mcp-Session-Id / sticky SSE), top-level resultType complete|input_required,
  HMAC-SHA256 requestState, agentgateway routing, modular testability.
-->

- **FR-001**: System MUST expose a migration-application capability that accepts a target cluster identifier and a migration script name.
- **FR-002**: When the script name indicates a destructive operation (presence of "drop" or "destructive", case-insensitive), the system MUST respond with an input-required outcome rather than completing the migration immediately.
- **FR-003**: An input-required outcome MUST include a top-level result status of `input_required`, a structured input request for boolean `confirm_drop` and string `environment_tag`, and a continuation handle that captures script details, issuance time, and target cluster.
- **FR-004**: The continuation handle MUST be integrity-protected with HMAC-SHA256 (and safely encoded for transport) so that tampering is detectable on resume.
- **FR-005**: On a resumed request that includes matching operator answers and a valid continuation handle, the system MUST verify the handle, then return a top-level result status of `complete` for successful authorized application (demo may simulate apply).
- **FR-006**: If the continuation handle fails verification, or required confirmation answers are missing/negative for a destructive migration, the system MUST fail closed and MUST NOT return successful completion of the destructive migration.
- **FR-007**: When the script name does not indicate destructive operations, the system MUST return `complete` without eliciting `confirm_drop` / `environment_tag`.
- **FR-008**: Migration tool invocations in the demo path MUST be routed through the configured API gateway (default port 8080); the primary demo MUST NOT rely on sticky session identifiers (including `Mcp-Session-Id`) or persistent waiting streams for the HITL pause.
- **FR-009**: The agent MUST connect to the configured local language-model endpoint using project environment settings, invoke the migration capability as part of fulfilling the operator prompt, and when an input-required outcome is received, transition to a human-input step.
- **FR-010**: During the human-input step, the system MUST prompt the operator in the terminal, collect values for the requested fields, build the answer map, and re-issue the migration request with the original continuation handle.
- **FR-011**: A single harness entrypoint MUST start the migration service, start the gateway proxy, trigger agent execution, and support the full HITL interaction without requiring the operator to manually orchestrate those pieces.
- **FR-012**: Protocol requests for the migration tool MUST declare the 2026-07-28 protocol version and identify the tools/call method and migration tool name expected by the demo contract.
- **FR-013**: Migration service, gateway configuration, and agent runloop MUST remain modular enough to be reasoned about and verified independently as well as together through the harness.

### Key Entities

- **Migration Request**: Cluster identifier, script name, and optional resume payload (operator answers + continuation handle).
- **Input-Required Outcome**: Result status `input_required`, list of field elicitations (`confirm_drop`, `environment_tag`), and continuation handle.
- **Continuation Handle (`requestState`)**: Opaque, integrity-protected token binding cluster, script details, and timestamp for stateless resume.
- **Completion Outcome**: Result status `complete` with a human-readable summary of authorized (or non-destructive) migration application.
- **Demo Run Session**: Harness-managed lifecycle linking gateway routing, migration service, agent pause/resume, and terminal operator interaction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a scripted destructive-migration demo, an operator can go from initial agent prompt to successful authorized completion in under 5 minutes, including the human confirmation step.
- **SC-002**: 100% of destructive-migration demos in the happy path show a distinct pause for confirmation before completion (no silent apply of drop-indicated scripts).
- **SC-003**: 100% of retries with a tampered continuation handle are rejected without reporting successful destructive migration completion.
- **SC-004**: After the input-required pause, the operator can finish the flow without restarting the overall demo session from the beginning.
- **SC-005**: A presenter can start the full demonstration from one harness command and complete the destructive HITL story without manually launching each component separately.
- **SC-006**: A non-destructive script name completes without a drop-confirmation prompt in the standard demo path.

## Assumptions

- Migration "application" in this demo is simulated or mocked; no real production database is required to prove the MRTR HITL contract.
- Destructive detection is based on script name keywords (`drop`, `destructive`), not deep SQL parsing, unless later expanded.
- Operator interaction is terminal-based for the first deliverable (no separate web UI).
- Local model serving and gateway processes are available on the operator's machine per project environment configuration.
- Shared HMAC secret and ports are supplied via environment configuration excluded from source control.
- Affirmative authorization means `confirm_drop` is true and `environment_tag` is a non-empty string.
- Round-robin / unpinned gateway routing is in scope as a design constraint; proving multi-instance physical failover may use a single instance plus absence of session stickiness as the demo evidence unless a multi-instance setup is added later.
