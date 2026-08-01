import os

from fastapi.testclient import TestClient

os.environ.setdefault("MCP_HMAC_SECRET", "contract-test-secret")

from mcp_server.mrtr_types import ELICITATION_KEY, ENVIRONMENT_TAGS, PROTOCOL_VERSION
from mcp_server.server import app

client = TestClient(app)


def test_destructive_returns_input_required_shape():
    response = client.post(
        "/mcp",
        headers={
            "Mcp-Protocol-Version": PROTOCOL_VERSION,
            "Content-Type": "application/json",
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
    body = response.json()
    result = body["result"]
    assert result["resultType"] == "input_required"
    assert "requestState" in result and "." in result["requestState"]
    assert ELICITATION_KEY in result["inputRequests"]
    elicit = result["inputRequests"][ELICITATION_KEY]
    assert elicit["method"] == "elicitation/create"
    assert elicit["params"]["mode"] == "form"
    enum_values = elicit["params"]["requestedSchema"]["properties"]["environment_tag"]["enum"]
    assert enum_values == list(ENVIRONMENT_TAGS)
