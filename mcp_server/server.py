"""FastAPI MCP 2026-07-28 Streamable HTTP endpoint for apply_db_migration."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

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


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    mcp_protocol_version: str | None = Header(default=None, alias="Mcp-Protocol-Version"),
    mcp_method: str | None = Header(default=None, alias="Mcp-Method"),
    mcp_name: str | None = Header(default=None, alias="Mcp-Name"),
    mcp_session_id: str | None = Header(default=None, alias="Mcp-Session-Id"),
) -> JSONResponse:
    # Constitution: never require sticky session headers. If a client sends one, ignore it.
    _ = mcp_session_id

    if mcp_protocol_version != PROTOCOL_VERSION:
        body = await request.json()
        return _jsonrpc_error(
            body.get("id") if isinstance(body, dict) else None,
            -32600,
            f"Mcp-Protocol-Version must be {PROTOCOL_VERSION}",
        )

    body = await request.json()
    if not isinstance(body, dict):
        return _jsonrpc_error(None, -32600, "Invalid JSON-RPC body")

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if mcp_method and mcp_method != method:
        return _jsonrpc_error(req_id, -32600, "Mcp-Method header does not match body method")

    if method != "tools/call":
        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    if not isinstance(params, dict):
        return _jsonrpc_error(req_id, -32602, "params must be an object")

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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
