# Quickstart: MRTR Database Migration HITL Demo

## Prerequisites

1. **Python 3.11+** and [`uv`](https://github.com/astral-sh/uv)
2. **LM Studio** running with model `qwen/qwen3.6-35b-a3b` on `http://127.0.0.1:1234/v1`
3. **agentgateway** binary on `PATH` ([install docs](https://agentgateway.dev/docs/standalone/latest/deployment/binary))

## Configure

```bash
cp .env.example .env
# Ensure at least:
# OPENAI_API_BASE=http://127.0.0.1:1234/v1
# OPENAI_API_KEY=lm-studio
# MODEL_NAME=qwen/qwen3.6-35b-a3b
# AGENTGATEWAY_PORT=8080
# MCP_SERVER_PORT=8000
# MCP_HMAC_SECRET=<random 32+ byte hex>
```

## Install deps

```bash
uv sync
```

## Run the demo (one command)

```bash
uv run python main.py
```

Harness responsibilities:

1. Fail-fast probe of LM Studio connectivity
2. Ensure `agentgateway.yaml` exists (`statefulMode: stateless`, port 8080 → MCP `:8000/mcp`)
3. Start MCP server (`uvicorn` / FastAPI on `MCP_SERVER_PORT`)
4. Start `agentgateway -f agentgateway.yaml`
5. Run LangGraph agent against gateway `:8080` with default prompt for `prod-db-01` / `V004__drop_legacy_users.sql`
6. On `input_required`, prompt terminal for `confirm_drop` and `environment_tag` (`dev`|`staging`|`prod`)
7. Retry tool call with `inputResponses` + `requestState`; print `complete` summary
8. Tear down child processes on exit

## Manual component checks (optional)

```bash
# MCP only
uv run uvicorn mcp_server.server:app --host 127.0.0.1 --port 8000

# Gateway only (requires MCP up)
agentgateway -f agentgateway.yaml

# Contract smoke (example)
curl -s http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Mcp-Protocol-Version: 2026-07-28' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"apply_db_migration","arguments":{"cluster_id":"prod-db-01","script_name":"V004__drop_legacy_users.sql"}}}'
```

## Expected happy path

1. Agent requests destructive migration  
2. Server returns `resultType: input_required` + HMAC `requestState`  
3. You enter `confirm_drop=true` and `environment_tag=prod`  
4. Server returns `resultType: complete` with simulated apply message  

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Fail-fast at start | LM Studio listening; `MODEL_NAME` loaded |
| `agentgateway` not found | Install binary; ensure `PATH` |
| Session header appears | Confirm `statefulMode: stateless` in `agentgateway.yaml` |
| HMAC errors on resume | Same `MCP_HMAC_SECRET`; resume within 5 minutes |
| Invalid environment tag | Must be exactly `dev`, `staging`, or `prod` |
