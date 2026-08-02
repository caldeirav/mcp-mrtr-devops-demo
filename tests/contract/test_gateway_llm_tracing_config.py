from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "agentgateway.yaml"


def test_gateway_yaml_has_llm_tracing_and_stateless_mcp():
    text = GATEWAY.read_text(encoding="utf-8")
    assert "frontendPolicies:" in text
    assert "tracing:" in text
    assert "host: localhost:4317" in text
    assert "randomSampling: true" in text
    assert "llm:" in text
    assert "baseUrl: http://127.0.0.1:1234/v1" in text
    assert "provider:" in text
    assert "custom:" in text
    assert "statefulMode: stateless" in text
    assert "devops-migration" in text
    assert "http://127.0.0.1:8000/mcp" in text
    # Constitution: do not advertise sticky session headers via CORS
    assert "exposeHeaders:" not in text
    assert "- Mcp-Session-Id" not in text
