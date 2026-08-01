import os

import httpx
import pytest

from mcp_server.mrtr_types import PROTOCOL_VERSION

GATEWAY = os.getenv("AGENTGATEWAY_URL", "http://127.0.0.1:8080")


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
                "Mcp-Protocol-Version": PROTOCOL_VERSION,
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
                },
            },
        )
    assert response.status_code == 200
    # Stateless gateway must not require session stickiness for success
    assert "mcp-session-id" not in {k.lower() for k in response.headers.keys()}
    body = response.json()
    assert body.get("result", {}).get("resultType") == "input_required"
