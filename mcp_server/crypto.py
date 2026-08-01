"""HMAC-SHA256 requestState minting and verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from mcp_server.mrtr_types import (
    REQUEST_STATE_TTL_SECONDS,
    RequestStatePayload,
)


class RequestStateError(Exception):
    """Raised when requestState fails integrity, TTL, or bind checks."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def mint_request_state(
    *,
    secret: str,
    cluster_id: str,
    script_name: str,
    iat: int | None = None,
) -> str:
    payload = RequestStatePayload(
        cluster_id=cluster_id,
        script_name=script_name,
        iat=iat if iat is not None else int(time.time()),
    )
    payload_json = payload.model_dump_json().encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_request_state(
    token: str,
    *,
    secret: str,
    cluster_id: str,
    script_name: str,
    now: int | None = None,
    ttl_seconds: int = REQUEST_STATE_TTL_SECONDS,
) -> RequestStatePayload:
    if not token or "." not in token:
        raise RequestStateError("requestState is missing or malformed")

    payload_b64, signature = token.rsplit(".", 1)
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise RequestStateError("requestState HMAC verification failed")

    try:
        raw = _b64url_decode(payload_b64)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        payload = RequestStatePayload.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - treat any parse issue as invalid state
        raise RequestStateError("requestState payload is invalid") from exc

    current = now if now is not None else int(time.time())
    if current - payload.iat > ttl_seconds:
        raise RequestStateError("requestState has expired")
    if payload.iat > current + 60:
        raise RequestStateError("requestState issuance time is invalid")

    if payload.cluster_id != cluster_id or payload.script_name != script_name:
        raise RequestStateError("requestState does not match migration arguments")

    return payload
