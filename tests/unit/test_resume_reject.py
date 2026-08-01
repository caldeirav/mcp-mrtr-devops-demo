import os

from fastapi.testclient import TestClient

os.environ["MCP_HMAC_SECRET"] = "resume-reject-secret"

from mcp_server.mrtr_types import ELICITATION_KEY, PROTOCOL_VERSION
from mcp_server.server import app

client = TestClient(app)


def _initial_destructive():
    return client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": PROTOCOL_VERSION},
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
    ).json()["result"]


def test_tampered_request_state_errors():
    result = _initial_destructive()
    token = result["requestState"]
    bad = token[:-4] + "dead"
    response = client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": PROTOCOL_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "apply_db_migration",
                "arguments": {
                    "cluster_id": "prod-db-01",
                    "script_name": "V004__drop_legacy_users.sql",
                },
                "requestState": bad,
                "inputResponses": {
                    ELICITATION_KEY: {
                        "action": "accept",
                        "content": {"confirm_drop": True, "environment_tag": "prod"},
                    }
                },
            },
        },
    )
    body = response.json()
    assert "error" in body
    assert "requestState" in body["error"]["message"]
