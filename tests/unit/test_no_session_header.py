"""Guard: client must not send Mcp-Session-Id."""

from agent.mcp_client import McpClient


def test_client_headers_omit_session_id():
    client = McpClient("http://127.0.0.1:8080")
    headers = client._headers()
    assert "Mcp-Session-Id" not in headers
    assert headers["MCP-Protocol-Version"] == "2026-07-28"
    assert headers["Accept"] == "application/json, text/event-stream"
    meta = client._request_meta()
    assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert "io.modelcontextprotocol/clientInfo" in meta
