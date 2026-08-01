import os

from fastapi.testclient import TestClient

os.environ["MCP_HMAC_SECRET"] = "deny-contract-secret"

from mcp_server.mrtr_types import ELICITATION_KEY, PROTOCOL_VERSION
from mcp_server.server import app

client = TestClient(app)


def _state_token() -> str:
    result = client.post(
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
    return result["requestState"]


def test_confirm_false_returns_denied_complete():
    token = _state_token()
    body = client.post(
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
                "requestState": token,
                "inputResponses": {
                    ELICITATION_KEY: {
                        "action": "accept",
                        "content": {"confirm_drop": False, "environment_tag": "prod"},
                    }
                },
            },
        },
    ).json()
    assert body["result"]["resultType"] == "complete"
    text = body["result"]["content"][0]["text"].lower()
    assert "denied" in text or "cancelled" in text
    assert "not applied" in text


def test_invalid_environment_tag_denied_complete():
    token = _state_token()
    body = client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": PROTOCOL_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "apply_db_migration",
                "arguments": {
                    "cluster_id": "prod-db-01",
                    "script_name": "V004__drop_legacy_users.sql",
                },
                "requestState": token,
                "inputResponses": {
                    ELICITATION_KEY: {
                        "action": "accept",
                        "content": {"confirm_drop": True, "environment_tag": "qa"},
                    }
                },
            },
        },
    ).json()
    assert body["result"]["resultType"] == "complete"
    assert "not applied" in body["result"]["content"][0]["text"].lower()
