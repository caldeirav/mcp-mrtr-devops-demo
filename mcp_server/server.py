"""FastAPI MCP 2026-07-28 Streamable HTTP endpoint for apply_db_migration."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from mcp_server.crypto import RequestStateError, mint_request_state, verify_request_state
from mcp_server.mrtr_types import (
    ELICITATION_KEY,
    ENVIRONMENT_TAGS,
    PROTOCOL_VERSION,
    TOOL_NAME,
    CompleteResult,
    ElicitFormParams,
    ElicitRequest,
    ElicitResult,
    InputRequiredResult,
    TextContent,
    build_confirm_drop_schema,
    is_destructive_script,
    is_valid_environment_tag,
)

app = FastAPI(title="MCP MRTR DevOps Demo", version="0.1.0")

SERVER_NAME = "mcp-mrtr-devops-demo"
SERVER_VERSION = "0.1.0"

# Prefer 2026-07-28; also accept common client/gateway versions used by playgrounds.
COMPATIBLE_PROTOCOL_VERSIONS = frozenset(
    {
        PROTOCOL_VERSION,
        "2025-11-25",
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
    }
)


def _hmac_secret() -> str:
    secret = os.getenv("MCP_HMAC_SECRET", "").strip()
    if not secret:
        raise RuntimeError("MCP_HMAC_SECRET is required")
    return secret


def _jsonrpc_error(req_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }
    )


def _jsonrpc_result(req_id: Any, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _complete_text(text: str) -> dict[str, Any]:
    return CompleteResult(content=[TextContent(text=text)]).model_dump()


def _tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": (
            "Apply a database migration script to a cluster. Destructive script names "
            "(containing 'drop' or 'destructive') yield SEP-2322 input_required HITL "
            "before simulated apply."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "string",
                    "description": "Target cluster identifier (default demo: prod-db-01)",
                },
                "script_name": {
                    "type": "string",
                    "description": (
                        "Migration script filename "
                        "(default demo: V004__drop_legacy_users.sql)"
                    ),
                },
            },
            "required": ["cluster_id", "script_name"],
        },
    }


def _resolve_protocol_version(
    header_version: str | None,
    body: dict[str, Any],
) -> str | None:
    """Prefer HTTP header, then params._meta, else None (caller may default)."""
    if header_version and header_version.strip():
        return header_version.strip()
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    nested = meta.get("io.modelcontextprotocol/protocolVersion")
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    plain = meta.get("protocolVersion")
    if isinstance(plain, str) and plain.strip():
        return plain.strip()
    return None


def _build_input_required(cluster_id: str, script_name: str) -> dict[str, Any]:
    token = mint_request_state(
        secret=_hmac_secret(),
        cluster_id=cluster_id,
        script_name=script_name,
    )
    elicit = ElicitRequest(
        params=ElicitFormParams(
            message=(
                f"Confirm destructive migration on {cluster_id} ({script_name}). "
                f"environment_tag must be one of: {', '.join(ENVIRONMENT_TAGS)}"
            ),
            requestedSchema=build_confirm_drop_schema(),
        )
    )
    return InputRequiredResult(
        inputRequests={ELICITATION_KEY: elicit},
        requestState=token,
    ).model_dump()


def _extract_elicitation(input_responses: dict[str, Any] | None) -> ElicitResult | None:
    if not input_responses or ELICITATION_KEY not in input_responses:
        return None
    try:
        return ElicitResult.model_validate(input_responses[ELICITATION_KEY])
    except Exception:  # noqa: BLE001
        return None


def _handle_apply_db_migration(params: dict[str, Any]) -> dict[str, Any] | tuple[int, str]:
    arguments = params.get("arguments") or {}
    cluster_id = (arguments.get("cluster_id") or "").strip()
    script_name = (arguments.get("script_name") or "").strip()
    if not cluster_id or not script_name:
        return -32602, "cluster_id and script_name are required"

    request_state = params.get("requestState")
    input_responses = params.get("inputResponses")

    # Resume path
    if request_state is not None or input_responses is not None:
        if not request_state:
            return -32602, "requestState is required on retry"
        try:
            verify_request_state(
                str(request_state),
                secret=_hmac_secret(),
                cluster_id=cluster_id,
                script_name=script_name,
            )
        except RequestStateError as exc:
            return -32000, f"Invalid requestState: {exc}"

        elicit = _extract_elicitation(input_responses if isinstance(input_responses, dict) else None)
        if elicit is None or elicit.action != "accept":
            return _complete_text(
                "Migration denied/cancelled: confirmation not accepted; not applied."
            )

        content = elicit.content or {}
        confirm_drop = content.get("confirm_drop")
        environment_tag = content.get("environment_tag")
        if confirm_drop is not True:
            return _complete_text(
                "Migration denied/cancelled: confirm_drop=false or missing; not applied."
            )
        if not isinstance(environment_tag, str) or not is_valid_environment_tag(environment_tag):
            return _complete_text(
                "Migration denied/cancelled: invalid environment_tag; "
                f"allowed={list(ENVIRONMENT_TAGS)}; not applied."
            )

        return _complete_text(
            f"Migration {script_name} applied on {cluster_id} "
            f"(environment_tag={environment_tag}) [simulated]."
        )

    # Initial path
    if is_destructive_script(script_name):
        return _build_input_required(cluster_id, script_name)

    return _complete_text(
        f"Migration {script_name} applied on {cluster_id} (non-destructive) [simulated]."
    )


def _handle_initialize(_params: dict[str, Any]) -> dict[str, Any]:
    # Advertise preferred modern version so playgrounds can continue after handshake.
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
        "instructions": (
            "SEP-2322 MRTR demo server. Call apply_db_migration; destructive scripts "
            "return resultType=input_required with HMAC requestState."
        ),
    }


def _handle_server_discover(_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "resultType": "complete",
        "supportedVersions": [PROTOCOL_VERSION],
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "instructions": (
            "Stateless MCP 2026-07-28 server demonstrating SEP-2322 multi round-trip "
            "HITL for destructive database migrations."
        ),
        "ttlMs": 3_600_000,
        "cacheScope": "public",
        "_meta": {
            "io.modelcontextprotocol/serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            }
        },
    }


def _handle_tools_list(_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "resultType": "complete",
        "tools": [_tool_definition()],
        "ttlMs": 3_600_000,
        "cacheScope": "public",
    }


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    mcp_protocol_version: str | None = Header(default=None, alias="Mcp-Protocol-Version"),
    mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
    mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
    mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
) -> Response:
    # Constitution: never require sticky session headers. If a client sends one, ignore it.
    _ = mcp_session_id

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return _jsonrpc_error(None, -32700, "Parse error")

    if not isinstance(body, dict):
        return _jsonrpc_error(None, -32600, "Invalid JSON-RPC body")

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _jsonrpc_error(req_id, -32602, "params must be an object")

    resolved_version = _resolve_protocol_version(mcp_protocol_version, body)
    # Playground/gateway may omit the header or send an older client version.
    # Accept compatible versions and default missing versions to the demo protocol.
    if resolved_version is None:
        resolved_version = PROTOCOL_VERSION
    elif resolved_version not in COMPATIBLE_PROTOCOL_VERSIONS:
        return _jsonrpc_error(
            req_id,
            -32600,
            f"Unsupported Mcp-Protocol-Version {resolved_version!r}; "
            f"supported={sorted(COMPATIBLE_PROTOCOL_VERSIONS)}",
        )

    if mcp_method and method and mcp_method != method:
        return _jsonrpc_error(req_id, -32600, "Mcp-Method header does not match body method")

    # JSON-RPC notifications have no id — acknowledge without a result body.
    if req_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)

    if method == "ping":
        return _jsonrpc_result(req_id, {})

    if method == "initialize":
        return _jsonrpc_result(req_id, _handle_initialize(params))

    if method == "server/discover":
        return _jsonrpc_result(req_id, _handle_server_discover(params))

    if method == "tools/list":
        return _jsonrpc_result(req_id, _handle_tools_list(params))

    if method == "tools/call":
        tool_name = params.get("name")
        if mcp_name and mcp_name != tool_name:
            return _jsonrpc_error(req_id, -32600, "Mcp-Name header does not match tool name")
        if tool_name != TOOL_NAME:
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {tool_name}")
        outcome = _handle_apply_db_migration(params)
        if isinstance(outcome, tuple):
            code, message = outcome
            return _jsonrpc_error(req_id, code, message)
        return _jsonrpc_result(req_id, outcome)

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
