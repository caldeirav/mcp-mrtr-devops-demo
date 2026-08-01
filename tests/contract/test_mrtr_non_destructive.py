import os

from fastapi.testclient import TestClient

os.environ.setdefault("MCP_HMAC_SECRET", "non-destructive-secret")

from mcp_server.mrtr_types import PROTOCOL_VERSION
from mcp_server.server import app

client = TestClient(app)


def test_non_destructive_completes_without_input_required():
    body = client.post(
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
                    "script_name": "V001__add_index.sql",
                },
            },
        },
    ).json()
    result = body["result"]
    assert result["resultType"] == "complete"
    assert "inputRequests" not in result
    assert "non-destructive" in result["content"][0]["text"].lower()
