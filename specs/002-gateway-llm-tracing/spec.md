# Feature Specification: Agentgateway LLM Playground & Trace Observability

**Feature Branch**: `002-gateway-llm-tracing`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Enhance the MCP MRTR DevOps demo to leverage agentgateway more fully for demos and screenshots: (1) Enable and create the agentgateway LLM configuration section so models from the local LM Studio OpenAI-compatible provider appear in the agentgateway admin UI / LLM playground—configure `llm` in `agentgateway.yaml` with a custom or openai-compatible provider targeting LM Studio at `http://127.0.0.1:1234/v1` (api key optional/local, default model from existing `.env` `MODEL_NAME` / `OPENAI_API_BASE` / `OPENAI_API_KEY`), keep MCP `devops-migration` target and `statefulMode: stateless`, document how to open the UI LLM section and verify listed models; optionally keep the LangGraph agent on direct LM Studio OR route agent chat through agentgateway LLM if low-friction. (2) Enable richer UI-style distributed traces with OTLP/Jaeger: configure agentgateway `frontendPolicies.tracing` to export OTLP gRPC to `localhost:4317` with full sampling for demos (`randomSampling: true`), add a documented local Jaeger all-in-one (Docker) startup (ports 16686 UI + 4317 OTLP), wire harness/`main.py` or README so demo operators can start Jaeger alongside MCP+gateway, and verify that MCP tool calls including SEP-2322 `input_required` / resume round-trips produce inspectable traces in Jaeger. Preserve constitution constraints (connection-stateless MCP, HMAC requestState, tools via gateway :8080, LM Studio as LLM). Update `.env.example`, README quickstart, and contracts under the new feature spec."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Local Models in the Gateway Console (Priority: P1)

A demo presenter opens the gateway admin console and uses the LLM configuration / playground area to see models served by the local model host already used by the demo. They can confirm the configured default model appears and send a simple chat-style probe from the console without changing the existing MCP migration target or connection-stateless gateway mode.

**Why this priority**: Makes agentgateway visibly part of the LLM story for screenshots and walkthroughs, not only a silent proxy for tools.

**Independent Test**: With the local model host running and the gateway started from updated demo configuration, open the admin console LLM section and verify at least the demo’s default model is listed and selectable; run a short playground prompt and receive a model response.

**Acceptance Scenarios**:

1. **Given** the local model host is serving the demo’s default model and the gateway is running with LLM provider configuration enabled, **When** the presenter opens the gateway admin console LLM section, **Then** they see the configured local provider and can identify the demo default model among available models.
2. **Given** the LLM section shows the default model, **When** the presenter sends a short test prompt from the playground, **Then** they receive a successful model reply routed through the gateway’s LLM path.
3. **Given** LLM configuration is enabled, **When** the presenter reviews MCP routing, **Then** the existing migration tool target remains available and the gateway continues to operate in connection-stateless mode for tools.

---

### User Story 2 - Inspect HITL Round-Trips in a Trace Viewer (Priority: P1)

A demo presenter enables local distributed tracing, runs the familiar destructive migration authorization story (pause for human confirmation, then resume), and opens a trace viewer UI to show gateway-mediated tool traffic—including the input-required pause and the resume that completes the migration—as inspectable spans suitable for screenshots.

**Why this priority**: Rich UI traces turn the SEP-2322 multi round-trip story into something audiences can see beyond the terminal.

**Independent Test**: Start the local trace backend, run one destructive migration HITL demo through the gateway, open the trace viewer, and locate spans covering the initial tool call and the continuation/resume call.

**Acceptance Scenarios**:

1. **Given** the local trace collector/viewer is running and gateway tracing is enabled with full sampling for demos, **When** the presenter runs the destructive migration story through the gateway, **Then** new traces appear in the viewer within a short interactive wait (typically under one minute after the flow completes).
2. **Given** a completed destructive HITL run, **When** the presenter opens the relevant trace, **Then** they can distinguish at least the initial migration tool invocation that required input and the later resume/completion invocation (two round trips visible as related or sequential spans).
3. **Given** tracing is enabled, **When** the migration story finishes successfully with valid operator approval, **Then** the functional HITL outcome is unchanged (authorization still pauses, resume still completes, migration still simulated only after approval).

---

### User Story 3 - Documented Demo Operator Path (Priority: P2)

A first-time demo operator follows the project quickstart to enable LLM console visibility and optional tracing without reverse-engineering configuration. Environment examples and contracts describe the new settings, ports, and verification steps alongside the existing harness flow.

**Why this priority**: Presenters need a repeatable path for talks and screenshots; undocumented console/trace setup will not be used.

**Independent Test**: A reader following only the updated quickstart/README can enable LLM console listing and (optionally) tracing, then complete User Stories 1 and 2 without unpublished tribal knowledge.

**Acceptance Scenarios**:

1. **Given** a clean checkout with example environment settings, **When** the operator follows the quickstart sections for LLM console and tracing, **Then** they know which services to start, which ports to open in a browser, and how to verify models and traces.
2. **Given** the operator does not want tracing for a short run, **When** they follow the default or documented “tracing optional” path, **Then** the core migration HITL demo still runs without requiring the trace viewer.

---

### User Story 4 - Agent Chat Path Remains Reliable (Priority: P3)

The LangGraph agent continues to complete the migration narrative using the local model host. Chat may remain direct to the local model host (default) so the HITL demo stays low-friction; routing agent chat through the gateway LLM path is only required if it can be done without complicating the primary story.

**Why this priority**: Protects the existing end-to-end demo; gateway LLM UI value must not regress the agent harness.

**Independent Test**: Run the existing one-command harness destructive happy path and confirm LLM narrative + HITL still succeed with the same operator experience.

**Acceptance Scenarios**:

1. **Given** updated gateway configuration that includes LLM and optional tracing, **When** the operator runs the standard harness for a destructive migration, **Then** the agent still validates the model host, pauses for confirmation, resumes with continuation state, and completes successfully.
2. **Given** agent chat remains on the direct local model path (default assumption), **When** the presenter uses the gateway LLM playground separately, **Then** both paths can use the same local model host without conflicting secrets committed to source control.

---

### Edge Cases

- Local model host is down: gateway LLM playground shows a clear failure; harness continues to fail fast on model validation before the HITL story (existing behavior).
- Trace backend is down while tracing is enabled: tool and HITL demo still succeed; presenter sees a clear warning that traces will not appear (demo must not hard-fail solely because the viewer is absent, unless the operator explicitly requested a “require traces” mode).
- Trace backend is up but sampling/misconfiguration yields empty UI: documentation includes a verification checklist (confirm sampling on, confirm collector port, re-run one tool call).
- Model list empty in console despite host up: documentation covers checking provider base URL/port alignment with the demo environment settings and that the default model is loaded in the local host.
- Non-destructive migration run: traces still appear for the single complete tool call; no input-required span pair is expected.
- Secrets and keys: local/demo API key values stay in environment examples only as non-secret placeholders; real secrets remain out of version control.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The demo gateway configuration MUST expose an LLM provider section that targets the same local OpenAI-compatible model host already used by the demo (base URL and default model driven by existing environment settings).
- **FR-002**: Presenters MUST be able to open the gateway admin console LLM / playground area and see the demo’s configured default model reflected for selection or use.
- **FR-003**: Presenters MUST be able to send a short chat-style probe from the gateway LLM playground against that local provider and receive a successful response when the model host is healthy.
- **FR-004**: MCP migration tooling configuration MUST remain available (`devops-migration` target equivalent) and MUST remain connection-stateless; sticky session headers MUST stay prohibited.
- **FR-005**: Gateway configuration MUST enable export of distributed traces to a local OTLP collector endpoint suitable for a demo trace viewer, with full sampling enabled for demonstration runs.
- **FR-006**: The project MUST document a one-command (or equivalently short) local trace viewer + OTLP collector startup path exposing a browser UI and an OTLP intake port aligned with the gateway tracing settings.
- **FR-007**: After a destructive migration HITL run through the gateway, presenters MUST be able to find inspectable traces covering the input-required tool round trip and the resume/completion round trip.
- **FR-008**: Core HITL semantics MUST remain unchanged: top-level result types `complete` | `input_required`, HMAC-protected continuation handles, tools invoked via the gateway (not bypassing it in the primary runloop).
- **FR-009**: Example environment documentation MUST list any new ports/flags related to LLM console usage and tracing without committing real secrets.
- **FR-010**: Quickstart / README MUST include verification steps for (a) models visible in the gateway LLM UI and (b) traces visible after an MRTR run.
- **FR-011**: Feature contracts under this spec MUST capture the updated gateway configuration expectations for LLM provider and tracing so later plan/tasks stay aligned.
- **FR-012**: The agent harness MUST continue to run the migration demo successfully with the new gateway settings; by default agent chat keeps using the direct local model host unless a low-friction gateway-routed chat path is explicitly adopted during planning without harming US1–US2.
- **FR-013**: When tracing is optional/disabled, the migration demo MUST still run end-to-end without requiring the trace viewer.
- **FR-014**: Existing constitutional infrastructure defaults remain in force: tools via gateway port 8080; local model host at the demo’s configured LM Studio endpoint and model name unless overridden by environment.

### Key Entities

- **LLM Provider Binding**: Association between the gateway console LLM section and the local model host (base URL, optional demo API key, default model identity).
- **Trace Export Policy**: Demo-oriented instruction that gateway request activity is copied to a local collector with full sampling.
- **Trace Viewer Session**: Browser-facing view where a presenter locates spans for MCP tool calls across pause and resume.
- **Demo Operator Guide**: Documented startup and verification steps spanning model host, gateway console, optional trace stack, and harness.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A presenter can open the gateway console LLM area and confirm the demo default model is available within 2 minutes of gateway + local model host being up.
- **SC-002**: At least 9 in 10 playground probe attempts against a healthy local model host return a visible successful reply in the console (excluding intentional model-host outages).
- **SC-003**: After one complete destructive HITL demo with tracing enabled, a presenter can locate pause and resume tool activity in the trace viewer within 3 minutes without reading source code.
- **SC-004**: Operators following the updated quickstart alone can enable LLM console visibility and optional tracing on the first attempt in a dry-run checklist (no missing ports or undocumented env vars).
- **SC-005**: Enabling LLM console configuration and optional tracing does not increase destructive happy-path demo wall time by more than 1 minute versus the pre-feature baseline on the same machine (excluding first-time image pulls for the trace stack).
- **SC-006**: With tracing disabled or the trace viewer absent, 100% of standard harness destructive happy-path runs that previously succeeded still succeed (no new hard dependency on the viewer for the core story).

## Assumptions

- Presenters already use the existing MCP MRTR demo stack (migration tool, connection-stateless gateway, local model host, interactive harness).
- **Default agent chat path**: Keep the LangGraph agent talking directly to the local model host; use the gateway LLM section primarily for console/playground demos and screenshots. Routing agent chat through the gateway is optional and only if planning shows it is low-friction.
- Local model host remains LM Studio OpenAI-compatible API at the constitution default endpoint/model unless overridden by environment.
- Trace stack for demos is a local all-in-one viewer that accepts OTLP (commonly Jaeger all-in-one via container) on the conventional demo ports (UI + OTLP gRPC); Docker (or equivalent) is available on presenter machines that want tracing screenshots.
- Full sampling is appropriate for demos; production-style sampling ratios are out of scope.
- Tracing is optional for the core HITL story; documentation and/or a simple flag make “no Docker / no traces” runs first-class.
- No change to HMAC continuation semantics, result types, or prohibition on sticky MCP sessions.
- Screenshot-oriented UX in third-party consoles (gateway admin UI, trace viewer) is accepted as-is; this feature configures and documents them rather than redesigning those UIs.
- Contracts, `.env.example`, and README/quickstart updates are in scope; marketing site posts are out of scope unless separately requested.
