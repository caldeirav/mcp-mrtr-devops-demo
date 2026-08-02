import os
from pathlib import Path

import httpx
import pytest

from mcp_server.mrtr_types import PROTOCOL_VERSION

GATEWAY = os.getenv("AGENTGATEWAY_URL", "http://127.0.0.1:8080")
ROOT = Path(__file__).resolve().parents[2]


def test_gateway_config_routes_mcp_without_jaeger_dependency():
    """Smoke: committed gateway config keeps MCP routing; Jaeger is optional."""
    text = (ROOT / "agentgateway.yaml").read_text(encoding="utf-8")
    assert "statefulMode: stateless" in text
    assert "devops-migration" in text
    assert "http://127.0.0.1:8000/mcp" in text
    # Tracing may be configured, but runtime must not require Jaeger to be up
    assert "ENABLE_JAEGER" not in text


def _gateway_up() -> bool:
    try:
        with httpx.Client(timeout=1.0) as client:
            client.post(f"{GATEWAY}/mcp", json={})
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _gateway_up(), reason="agentgateway not available on :8080")
def test_gateway_destructive_input_required():
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{GATEWAY}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": PROTOCOL_VERSION,
                "Mcp-Method": "tools/call",
                "Mcp-Name": "apply_db_migration",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "apply_db_migration",
                    "arguments": {
                        "cluster_id": "prod-db-01",
                        "script_name": "V004__drop_legacy_users.sql",
                    },
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
                        "io.modelcontextprotocol/clientInfo": {
                            "name": "pytest-integration",
                            "version": "0",
                        },
                        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}},
                    },
                },
            },
        )
    assert response.status_code == 200
    # Stateless gateway must not require session stickiness for success
    assert "mcp-session-id" not in {k.lower() for k in response.headers.keys()}
    # Gateway may return JSON or SSE
    if "text/event-stream" in response.headers.get("content-type", ""):
        data_line = next(
            line for line in reversed(response.text.splitlines()) if line.startswith("data:")
        )
        import json

        body = json.loads(data_line[len("data:") :].strip())
    else:
        body = response.json()
    assert body.get("result", {}).get("resultType") == "input_required"
