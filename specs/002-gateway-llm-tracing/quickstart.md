# Quickstart: Gateway LLM Console + Jaeger Traces

**Feature**: `002-gateway-llm-tracing`  
**Prerequisites**: Existing MRTR demo setup (LM Studio, `uv`, `agentgateway` binary, Docker optional for traces).

## 1. Environment

```bash
cd /path/to/mcp-mrtr-devops-demo
cp -n .env.example .env   # if needed
# Ensure:
#   OPENAI_API_BASE=http://127.0.0.1:1234/v1
#   OPENAI_API_KEY=lm-studio
#   MODEL_NAME=qwen/qwen3.6-35b-a3b
#   ENABLE_JAEGER=0          # set 1 to auto-start Jaeger from harness (when implemented)
```

Keep `MODEL_NAME` aligned with `llm.models[].params.model` in `agentgateway.yaml`.

## 2. Sync gateway config

Copy or ensure repo-root `agentgateway.yaml` matches  
`specs/002-gateway-llm-tracing/contracts/agentgateway.yaml`.

Validate:

```bash
export OPENAI_API_KEY=lm-studio
agentgateway -f agentgateway.yaml --validate-only
```

## 3. LLM playground (User Story 1)

1. Start LM Studio server with the demo model loaded.
2. Start the demo (harness or MCP + agentgateway) so the gateway is up on `:8080` and admin UI on `:15000`.
3. Open [http://localhost:15000/ui/](http://localhost:15000/ui/).
4. Open the **LLM** / playground area.
5. Select/confirm `qwen/qwen3.6-35b-a3b` (or the loaded LM Studio model).
6. Send a short probe prompt; confirm a reply.

MCP **Tool Playground** for `apply_db_migration` should still work (`statefulMode: stateless`).

## 4. Optional Jaeger traces (User Story 2)

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
# or: docker start jaeger
```

1. Run the destructive HITL demo (`uv run python main.py`) and complete pause → approve → resume.
2. Open [http://localhost:16686](http://localhost:16686).
3. Locate recent traces; identify the initial tool call and the resume/completion call.

If Jaeger is not running, the HITL demo must still succeed.

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
uv run python main.py
```

Destructive happy path (cluster `prod-db-01`, script `V004__drop_legacy_users.sql`) must still pause for HITL and complete after approval.
