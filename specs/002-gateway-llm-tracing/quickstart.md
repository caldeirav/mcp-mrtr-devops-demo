# Quickstart: Gateway LLM Console + Jaeger Traces

**Feature**: `002-gateway-llm-tracing`  
**Prerequisites**: Existing MRTR demo setup (LM Studio, `uv`, `agentgateway` binary, Docker optional for traces).

## 1. Environment

```bash
cd /path/to/mcp-mrtr-devops-demo
cp -n .env.example .env   # if needed
```

Ensure `.env` includes:

```bash
OPENAI_API_BASE=http://127.0.0.1:1234/v1
OPENAI_API_KEY=lm-studio
MODEL_NAME=qwen/qwen3.6-35b-a3b
ENABLE_JAEGER=0          # set 1 to auto-start/reuse Jaeger from main.py
```

Keep `MODEL_NAME` aligned with `llm.models[].params.model` in `agentgateway.yaml`.  
Never commit a real `.env` (gitignored).

## 2. Sync / validate gateway config

Repo-root `agentgateway.yaml` should match  
`specs/002-gateway-llm-tracing/contracts/agentgateway.yaml`.

```bash
export OPENAI_API_KEY=lm-studio
agentgateway -f agentgateway.yaml --validate-only
```

Harness fallback (if root file missing) copies from the **002** contract path in `main.py`.

## 3. LLM playground (User Story 1)

1. Start LM Studio server with the demo model loaded.
2. Start the demo so the gateway is up:

   ```bash
   uv run python main.py
   ```

   Or start MCP + `agentgateway -f agentgateway.yaml` separately (ensure `OPENAI_API_KEY` is in the gateway process environment).
3. Open [http://localhost:15000/ui/](http://localhost:15000/ui/).
4. Open the **LLM** / playground area.
5. Select/confirm `qwen/qwen3.6-35b-a3b` (or the loaded LM Studio model).
6. Send a short probe prompt; confirm a reply.

MCP **Tool Playground** for `apply_db_migration` should still work (`statefulMode: stateless`).

**Note**: LangGraph agent chat remains on **direct** LM Studio (`OPENAI_API_BASE`). Gateway `llm` is for the admin playground.

## 4. Optional Jaeger traces (User Story 2)

Tracing export is always configured (`frontendPolicies.tracing` → `localhost:4317`, `randomSampling: true`).  
Runtime collector is optional.

### Via harness

```bash
# .env
ENABLE_JAEGER=1
uv run python main.py
```

Behavior (`main.py`):

- Starts or reuses Docker container named `jaeger` (`jaegertracing/all-in-one:latest`, ports `16686`/`4317`).
- On failure (no Docker, port conflict, etc.): **warns and continues** — HITL is not blocked.
- On exit: if the harness started/restarted Jaeger for this run, it runs `docker stop jaeger` (never `docker rm`).

### Manual Docker

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
# or: docker start jaeger
```

### Verify pause / resume spans

1. Run the destructive HITL demo and complete pause → approve → resume.
2. Open [http://localhost:16686](http://localhost:16686).
3. Locate recent traces; identify the initial tool call and the resume/completion call.

If Jaeger is not running (`ENABLE_JAEGER=0`), the HITL demo must still succeed.

## 5. Ports cheat sheet

| Port | Service |
| --- | --- |
| `1234` | LM Studio OpenAI API |
| `8000` | MCP server |
| `8080` | agentgateway MCP proxy |
| `15000` | agentgateway admin UI |
| `4317` | OTLP gRPC (Jaeger) |
| `16686` | Jaeger UI |

## 6. Regression check

With or without Jaeger:

```bash
uv run pytest tests/ -q
uv run python main.py
```

Destructive happy path (cluster `prod-db-01`, script `V004__drop_legacy_users.sql`) must still pause for HITL and complete after approval.
