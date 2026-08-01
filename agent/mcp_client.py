"""HTTP client for MCP 2026-07-28 tools/call with MRTR parsing."""

from __future__ import annotations

from typing import Any

import httpx

from mcp_server.mrtr_types import (
    ELICITATION_KEY,
    PROTOCOL_VERSION,
    TOOL_NAME,
)


class McpClientError(Exception):
    """Raised for transport or JSON-RPC protocol errors."""


class McpClient:
    def __init__(self, base_url: str, *, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._next_id = 1

    def _headers(self) -> dict[str, str]:
        # Do not set Mcp-Session-Id — constitution forbids sticky sessions.
        return {
            "Content-Type": "application/json",
            "Mcp-Protocol-Version": PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
            "Mcp-Name": TOOL_NAME,
        }

    def _next_rpc_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value

    def call_apply_db_migration(
        self,
        *,
        cluster_id: str,
        script_name: str,
        request_state: str | None = None,
        input_responses: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "name": TOOL_NAME,
            "arguments": {
                "cluster_id": cluster_id,
                "script_name": script_name,
            },
        }
        if request_state is not None:
            params["requestState"] = request_state
        if input_responses is not None:
            params["inputResponses"] = input_responses

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_rpc_id(),
            "method": "tools/call",
            "params": params,
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        body = response.json()
        if "error" in body and body["error"]:
            err = body["error"]
            raise McpClientError(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
        result = body.get("result")
        if not isinstance(result, dict) or "resultType" not in result:
            raise McpClientError("MCP result missing resultType")
        if result["resultType"] not in ("complete", "input_required"):
            raise McpClientError(f"Unsupported resultType: {result['resultType']}")
        return result

    @staticmethod
    def build_input_responses(*, confirm_drop: bool, environment_tag: str) -> dict[str, Any]:
        return {
            ELICITATION_KEY: {
                "action": "accept",
                "content": {
                    "confirm_drop": confirm_drop,
                    "environment_tag": environment_tag,
                },
            }
        }

    @staticmethod
    def result_text(result: dict[str, Any]) -> str:
        content = result.get("content") or []
        texts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(t for t in texts if t) or str(result)
