# Data Model: MRTR Database Migration HITL Demo

**Date**: 2026-08-01  
**Aligns with**: [MCP MRTR schema](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr) + feature clarifications

## Canonical constants

```python
ENVIRONMENT_TAGS: Final[tuple[str, ...]] = ("dev", "staging", "prod")  # single allow-list
REQUEST_STATE_TTL_SECONDS: Final[int] = 300
DESTRUCTIVE_KEYWORDS: Final[tuple[str, ...]] = ("drop", "destructive")
DEFAULT_CLUSTER_ID: Final[str] = "prod-db-01"
DEFAULT_SCRIPT_NAME: Final[str] = "V004__drop_legacy_users.sql"
PROTOCOL_VERSION: Final[str] = "2026-07-28"
TOOL_NAME: Final[str] = "apply_db_migration"
ELICITATION_KEY: Final[str] = "confirm_drop_form"
```

## SEP-2322 / demo types (implement in `mcp_server/mrtr_types.py`)

Prefer **Pydantic v2 `BaseModel`** (listed dependency) with dataclass-equivalent field sets. Pure `@dataclass` mirrors are acceptable for unit tests if kept in sync.

### ResultType

```python
ResultType = Literal["complete", "input_required"]
```

### RequestStatePayload (server-internal; never sent plaintext without MAC)

| Field | Type | Rules |
| --- | --- | --- |
| `cluster_id` | `str` | non-empty; must match retry args |
| `script_name` | `str` | non-empty; must match retry args |
| `iat` | `int` | unix seconds; reject if `now - iat > 300` |
| `method` | `str` | `"tools/call"` |
| `tool` | `str` | `"apply_db_migration"` |

Wire format `requestState: str` = `base64url(json(payload)) + "." + hmac_sha256_hex(secret, payload_b64)`.

### ElicitFormParams / InputRequest entry

| Field | Type | Notes |
| --- | --- | --- |
| `method` | `Literal["elicitation/create"]` | |
| `params.mode` | `Literal["form"]` | |
| `params.message` | `str` | operator-facing prompt |
| `params.requestedSchema` | JSON Schema object | properties: `confirm_drop` bool, `environment_tag` string enum |

`InputRequests` = `dict[str, ElicitRequest]` (demo uses one key `confirm_drop_form`).

### InputRequiredResult

| Field | Type | Required |
| --- | --- | --- |
| `resultType` | `Literal["input_required"]` | yes |
| `inputRequests` | `InputRequests` | yes (demo) |
| `requestState` | `str` | yes (demo) |

At least one of `inputRequests` / `requestState` required by SEP; demo always sends both.

### ElicitResult / InputResponses entry

| Field | Type | Rules |
| --- | --- | --- |
| `action` | `Literal["accept", "decline", "cancel"]` | demo happy-path uses `accept` |
| `content` | `dict` | must include `confirm_drop: bool`, `environment_tag: str` when accepted |

`InputResponses` = `dict[str, ElicitResult]` keyed identically to `inputRequests`.

### CompleteResult (tool)

| Field | Type | Notes |
| --- | --- | --- |
| `resultType` | `Literal["complete"]` | yes |
| `content` | `list[{type: "text", text: str}]` | human-readable apply / deny summary |
| `isError` | `bool` | optional; prefer false + deny messaging for soft deny |

### ApplyDbMigrationArgs

| Field | Type | Rules |
| --- | --- | --- |
| `cluster_id` | `str` | required |
| `script_name` | `str` | required; destructive if keyword in name (case-insensitive) |
| `requestState` | `str \| None` | present on retry |
| `inputResponses` | `InputResponses \| None` | present on retry |

## Entities (domain)

### MigrationRequest

- Maps to tool arguments + optional resume fields.
- Default demo identity: `prod-db-01` / `V004__drop_legacy_users.sql`.

### ContinuationHandle

- Opaque `requestState` string; integrity via HMAC; TTL 5 minutes.

### EnvironmentTagAllowList

- `{dev, staging, prod}` — one constant module-level tuple/list.

### DemoRunSession (harness)

- Process handles: uvicorn MCP, agentgateway subprocess
- LangGraph `thread_id`
- Env: ports, HMAC secret, LLM base URL

## State transitions

```text
[tools/call initial]
       │
       ├─ non-destructive ──► CompleteResult (applied/simulated)
       │
       └─ destructive, no resume ──► InputRequiredResult
                                          │
                     client interrupt + terminal input
                                          │
                               [tools/call retry]
                                          │
              ├─ bad/expired/tampered requestState ──► JSON-RPC error
              ├─ decline / bad tag / missing fields ──► CompleteResult (denied)
              └─ confirm_drop true + allow-listed tag ──► CompleteResult (applied)
```

## Validation rules summary

| Condition | Outcome |
| --- | --- |
| Missing `cluster_id` / `script_name` | JSON-RPC / HTTP error before MRTR |
| Destructive + no valid resume | `input_required` |
| HMAC fail / TTL expire / bind mismatch | protocol error (not applied) |
| `confirm_drop` false or tag ∉ allow-list | `complete` + denied summary |
| `confirm_drop` true + tag ∈ allow-list | `complete` + applied summary |
