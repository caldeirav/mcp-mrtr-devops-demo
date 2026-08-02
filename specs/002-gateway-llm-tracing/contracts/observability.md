# Contract: Demo Observability (OTLP → Jaeger)

**Feature**: `002-gateway-llm-tracing`

## Gateway export

Agentgateway MUST include:

```yaml
frontendPolicies:
  tracing:
    host: localhost:4317
    randomSampling: true
```

| Setting | Demo value | Notes |
| --- | --- | --- |
| OTLP endpoint | `localhost:4317` | gRPC |
| Sampling | `true` (all requests) | Screenshot-friendly |

## Jaeger all-in-one

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

| Port | Purpose |
| --- | --- |
| `16686` | Jaeger UI |
| `4317` | OTLP gRPC intake |

Reuse existing container if name `jaeger` already running:

```bash
docker start jaeger
```

## Verification (destructive HITL)

1. Start Jaeger, LM Studio, then demo harness (or gateway + MCP).
2. Complete pause → approve → resume for `apply_db_migration`.
3. Open `http://localhost:16686`.
4. Find recent traces for gateway/MCP traffic.
5. Confirm **two** tool round-trips are distinguishable (initial `input_required` path and resume/`complete` path). Exact span attribute names may vary by agentgateway version; presence of two sequential MCP/`tools/call` activities is sufficient.

## Failure modes

| Condition | Expected demo behavior |
| --- | --- |
| Jaeger down, tracing configured | HITL demo succeeds; operator warned that traces will be empty |
| `ENABLE_JAEGER=0` (default) | No Docker requirement; core demo unchanged |
| Empty UI after run | Recheck `:4317` listening, `randomSampling: true`, re-run one tool call |

## Out of scope

- OpenTelemetry Collector multi-service compose
- Production sampling ratios
- Changing SEP-2322 payload shapes for span enrichment
