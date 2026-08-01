"""SEP-2322 MRTR types and canonical demo constants."""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

ENVIRONMENT_TAGS: Final[tuple[str, ...]] = ("dev", "staging", "prod")
REQUEST_STATE_TTL_SECONDS: Final[int] = 300
DESTRUCTIVE_KEYWORDS: Final[tuple[str, ...]] = ("drop", "destructive")
DEFAULT_CLUSTER_ID: Final[str] = "prod-db-01"
DEFAULT_SCRIPT_NAME: Final[str] = "V004__drop_legacy_users.sql"
PROTOCOL_VERSION: Final[str] = "2026-07-28"
TOOL_NAME: Final[str] = "apply_db_migration"
ELICITATION_KEY: Final[str] = "confirm_drop_form"
METHOD_TOOLS_CALL: Final[str] = "tools/call"

ResultType = Literal["complete", "input_required"]


def is_destructive_script(script_name: str) -> bool:
    lowered = script_name.lower()
    return any(keyword in lowered for keyword in DESTRUCTIVE_KEYWORDS)


def is_valid_environment_tag(tag: str) -> bool:
    return tag in ENVIRONMENT_TAGS


class RequestStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: str
    script_name: str
    iat: int
    method: str = METHOD_TOOLS_CALL
    tool: str = TOOL_NAME


class ElicitFormParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: Literal["form"] = "form"
    message: str
    requestedSchema: dict[str, Any]


class ElicitRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: Literal["elicitation/create"] = "elicitation/create"
    params: ElicitFormParams


class InputRequiredResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    resultType: Literal["input_required"] = "input_required"
    inputRequests: dict[str, ElicitRequest]
    requestState: str


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class CompleteResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    resultType: Literal["complete"] = "complete"
    content: list[TextContent]
    isError: bool = False


class ElicitResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: Literal["accept", "decline", "cancel"] = "accept"
    content: dict[str, Any] = Field(default_factory=dict)


class ApplyDbMigrationArgs(BaseModel):
    model_config = ConfigDict(extra="allow")

    cluster_id: str
    script_name: str


def build_confirm_drop_schema() -> dict[str, Any]:
    """JSON Schema for elicitation; enum sourced from ENVIRONMENT_TAGS only."""
    return {
        "type": "object",
        "properties": {
            "confirm_drop": {
                "type": "boolean",
                "description": "Confirm DROP/destructive ops",
            },
            "environment_tag": {
                "type": "string",
                "enum": list(ENVIRONMENT_TAGS),
                "description": "Target environment tag",
            },
        },
        "required": ["confirm_drop", "environment_tag"],
    }
