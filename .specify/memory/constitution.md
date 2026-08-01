<!--
Sync Impact Report:
- Version change: (template/unversioned) → 1.0.0
- Modified principles: (placeholders) →
  I. Connection Statelessness,
  II. Protocol Precision,
  III. HMAC Integrity,
  IV. Infrastructure Integration,
  V. Modular Verification
- Added sections: Protocol & Security Constraints; Development Workflow
- Removed sections: none (template placeholders replaced)
- Templates:
  - .specify/templates/plan-template.md ✅ updated (Constitution Check gates)
  - .specify/templates/spec-template.md ✅ aligned (no structural change required)
  - .specify/templates/tasks-template.md ✅ updated (module path conventions)
  - .specify/templates/commands/*.md ⚠ pending (directory absent)
- Follow-up TODOs: none
-->

# MCP MRTR DevOps Demo Constitution

## Core Principles

### I. Connection Statelessness

Every MCP interaction MUST be connection-stateless. The system MUST NOT open or
retain persistent SSE GET sockets, and MUST NOT use sticky session headers.
The `Mcp-Session-Id` header is strictly prohibited in client and server code,
configuration, and gateway routing. Continuity across round trips MUST rely
solely on signed `requestState` handles (see Principle III), never on
transport-level session affinity.

**Rationale**: SEP-2322 MRTR is designed for horizontally scalable, restart-safe
agents. Sticky sessions and long-lived SSE GETs reintroduce state that defeats
the demonstration and breaks multi-instance deployments.

### II. Protocol Precision

Every tool that participates in multi-round-trip flows MUST return a JSON-RPC
response whose payload includes a top-level `resultType` field. Allowed values
are exclusively `complete` and `input_required`. Responses MUST NOT omit
`resultType`, invent alternate enumerations, or encode completion status only
in nested or free-text fields. When `resultType` is `input_required`, the
response MUST carry the continuation material required for the next round trip
(including a signed `requestState` per Principle III).

**Rationale**: Agents, gateways, and tests all branch on `resultType`. Ambiguous
or non-conforming shapes make HITL loops unreliable and unverifiable.

### III. HMAC Integrity

All `requestState` continuation handles MUST be encrypted and signed with
HMAC-SHA256 using a shared secret (`MCP_HMAC_SECRET` or equivalent). On every
continuation, the receiver MUST verify the HMAC before trusting or mutating
state. Tampered, truncated, or re-signed handles MUST be rejected with a clear
protocol error. Plaintext or unsigned continuation blobs are forbidden.

**Rationale**: Stateless round trips move trust into the handle. HMAC-SHA256
guarantees tampered-state detection without server-side session storage.

### IV. Infrastructure Integration

All tool invocations MUST be routed through agentgateway on port 8080. The
local LLM MUST be LM Studio at `http://127.0.0.1:1234/v1` using model
`qwen/qwen3.6-35b-a3b`. Direct client-to-MCP-server tool calls that bypass the
gateway are forbidden in the demo runloop. Environment configuration MUST keep
gateway port, MCP server port, LLM base URL, and model name externally
configurable (e.g. via `.env`) without hardcoding secrets into source.

**Rationale**: The demo proves the full path—LangGraph client → agentgateway →
MCP server → LLM—not a shortcut that hides gateway or model integration.

### V. Modular Verification

The codebase MUST maintain clean, testable separation among three modules:
(1) the MCP server, (2) agentgateway configuration/routing, and (3) the
LangGraph client runloop. Each module MUST be independently startable and
testable. Cross-module contracts (JSON-RPC shapes, `resultType`, HMAC
`requestState`) MUST be covered by contract or integration tests. Shared
business logic MUST NOT be duplicated across module boundaries without an
explicit shared library.

**Rationale**: Modular boundaries make protocol and security regressions
localizable and keep the demo explainable component-by-component.

## Protocol & Security Constraints

- MCP protocol target: 2026-07-28 (stateless agent / SEP-2322 MRTR).
- Forbidden: persistent SSE GET session sockets; `Mcp-Session-Id`; unsigned
  `requestState`; gateway bypass for tool calls in the primary runloop.
- Required: HMAC-SHA256 for continuation handles; top-level `resultType` of
  `complete` or `input_required` on MRTR tool responses.
- Secrets (`MCP_HMAC_SECRET`, API keys) MUST live in environment/config files
  excluded from version control; MUST NOT be committed in source.

## Development Workflow

- Specs, plans, and tasks MUST pass the Constitution Check gates in
  `plan-template.md` before implementation proceeds past research.
- New tools or continuation flows MUST document `resultType` behavior and
  HMAC `requestState` lifecycle in the feature spec or contracts.
- Verification MUST exercise modules in isolation where feasible, then the
  full path through agentgateway (port 8080) with LM Studio.
- PRs and reviews MUST reject introductions of session stickiness,
  missing `resultType`, or unsigned continuation handles.

## Governance

This constitution supersedes conflicting informal practices in the repository.
Amendments MUST update `.specify/memory/constitution.md`, bump
`CONSTITUTION_VERSION` using semantic versioning (MAJOR for incompatible
principle removals/redefinitions; MINOR for new or materially expanded
principles; PATCH for clarifications), set **Last Amended** to the change date,
and propagate impacts to dependent templates (plan, spec, tasks) when gates or
mandatory sections change. Compliance review is expected at plan-time
(Constitution Check) and at PR review for any change touching MCP transport,
tool response shapes, HMAC handling, gateway routing, or module boundaries.

**Version**: 1.0.0 | **Ratified**: 2026-08-01 | **Last Amended**: 2026-08-01
