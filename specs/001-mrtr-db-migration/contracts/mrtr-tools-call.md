# Contract: `tools/call` — `apply_db_migration` (MCP 2026-07-28 MRTR)

**Base URL (via gateway)**: `http://127.0.0.1:8080`  
**Upstream MCP**: `http://127.0.0.1:8000/mcp`  
**Method**: `POST`  
**Path**: `/mcp` (gateway forwards to MCP target)

## Mandatory request headers

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `Accept` | `application/json, text/event-stream` |
| `MCP-Protocol-Version` | `2026-07-28` |
| `Mcp-Method` | `tools/call` |
| `Mcp-Name` | `apply_db_migration` |

**Forbidden**: `Mcp-Session-Id` (must not be required or emitted for demo success path).

`params._meta` MUST include modern MCP 2026-07-28 keys (enforced by agentgateway):

- `io.modelcontextprotocol/protocolVersion`
- `io.modelcontextprotocol/clientInfo`
- `io.modelcontextprotocol/clientCapabilities`

Gateway responses may be `Content-Type: text/event-stream` with a `data:` JSON-RPC payload.

## Initial call (destructive)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "apply_db_migration",
    "arguments": {
      "cluster_id": "prod-db-01",
      "script_name": "V004__drop_legacy_users.sql"
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientInfo": {"name": "mcp-mrtr-devops-demo", "version": "0.1.0"},
      "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}}
    }
  }
}
```

### Response — `input_required`

HTTP 200

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "input_required",
    "inputRequests": {
      "confirm_drop_form": {
        "method": "elicitation/create",
        "params": {
          "mode": "form",
          "message": "Confirm destructive migration on prod-db-01 (V004__drop_legacy_users.sql)",
          "requestedSchema": {
            "type": "object",
            "properties": {
              "confirm_drop": { "type": "boolean", "description": "Confirm DROP/destructive ops" },
              "environment_tag": {
                "type": "string",
                "enum": ["dev", "staging", "prod"],
                "description": "Target environment tag"
              }
            },
            "required": ["confirm_drop", "environment_tag"]
          }
        }
      }
    },
    "requestState": "<base64url_payload>.<hmac_sha256_hex>"
  }
}
```

## Retry call (after HITL)

`id` MUST be a new JSON-RPC id. Echo `requestState` unmodified.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "apply_db_migration",
    "arguments": {
      "cluster_id": "prod-db-01",
      "script_name": "V004__drop_legacy_users.sql"
    },
    "requestState": "<same opaque string>",
    "inputResponses": {
      "confirm_drop_form": {
        "action": "accept",
        "content": {
          "confirm_drop": true,
          "environment_tag": "prod"
        }
      }
    }
  }
}
```

> Note: If upstream schema nests `requestState` / `inputResponses` under `arguments` instead of `params`, implementation MUST pick one layout and keep client/server/contract tests identical. Preferred: siblings of `arguments` under `params` as above (MRTR retry fields on the call).

### Response — authorized `complete`

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "resultType": "complete",
    "content": [
      {
        "type": "text",
        "text": "Migration V004__drop_legacy_users.sql applied on prod-db-01 (environment_tag=prod) [simulated]."
      }
    ]
  }
}
```

### Response — denied `complete`

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "resultType": "complete",
    "content": [
      {
        "type": "text",
        "text": "Migration denied/cancelled: confirm_drop=false or invalid environment_tag; not applied."
      }
    ]
  }
}
```

### Response — tampered/expired state

JSON-RPC error object (not `resultType: complete`), e.g. code `-32602` / custom application error with message indicating invalid `requestState`.

## Non-destructive call

Script name without `drop`/`destructive` → immediate `resultType: "complete"` without `inputRequests`.
