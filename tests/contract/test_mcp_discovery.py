import os

from fastapi.testclient import TestClient

os.environ.setdefault("MCP_HMAC_SECRET", "discovery-test-secret")

from mcp_server.mrtr_types import PROTOCOL_VERSION, TOOL_NAME
from mcp_server.server import app

client = TestClient(app)


def test_tools_list_without_protocol_header():
    body = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    ).json()
    result = body["result"]
    assert result["resultType"] == "complete"
    names = [t["name"] for t in result["tools"]]
    assert TOOL_NAME in names


def test_tools_list_with_legacy_protocol_header():
    body = client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": "2025-11-25"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ).json()
    assert "error" not in body
    assert body["result"]["tools"][0]["name"] == TOOL_NAME


def test_initialize_advertises_modern_version():
    body = client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": "2025-03-26"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "playground", "version": "0"},
            },
        },
    ).json()
    assert body["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in body["result"]["capabilities"]


def test_server_discover():
    body = client.post(
        "/mcp",
        headers={"Mcp-Protocol-Version": PROTOCOL_VERSION},
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "server/discover",
            "params": {},
        },
    ).json()
    assert body["result"]["resultType"] == "complete"
    assert PROTOCOL_VERSION in body["result"]["supportedVersions"]
