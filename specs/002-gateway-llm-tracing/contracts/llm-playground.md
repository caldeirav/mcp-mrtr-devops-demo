# Contract: Gateway LLM Playground ↔ LM Studio

**Feature**: `002-gateway-llm-tracing`

## Provider binding

| Item | Value |
| --- | --- |
| Provider | `custom` with `formats: [completions]` |
| Base URL | `http://127.0.0.1:1234/v1` |
| Default model | `qwen/qwen3.6-35b-a3b` (sync with `MODEL_NAME`) |
| API key | `$OPENAI_API_KEY` → local placeholder `lm-studio` |
| Match | `name: "*"` |

## Operator verification

1. LM Studio local server running; default model loaded.
2. `export OPENAI_API_KEY=lm-studio` (or load `.env`) before starting agentgateway.
3. Start gateway with contract YAML; open `http://localhost:15000/ui/`.
4. Open **LLM** / playground section.
5. Confirm demo model is listed or selectable.
6. Send a short prompt (e.g. “Reply with the single word: pong”).
7. Expect a successful model reply when LM Studio is healthy.

## Non-goals

- LangGraph MUST continue using direct `OPENAI_API_BASE` (not required to proxy chat through gateway LLM in this feature).
- MCP target `devops-migration` and `statefulMode: stateless` MUST remain unchanged.
