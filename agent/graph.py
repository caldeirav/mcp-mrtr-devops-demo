"""LangGraph MRTR HITL runloop for apply_db_migration."""

from __future__ import annotations

import os
from typing import Any, Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent import console
from agent.mcp_client import McpClient, McpClientError
from mcp_server.mrtr_types import (
    DEFAULT_CLUSTER_ID,
    DEFAULT_SCRIPT_NAME,
    ENVIRONMENT_TAGS,
)


class AgentState(TypedDict, total=False):
    user_prompt: str
    cluster_id: str
    script_name: str
    llm_note: str
    request_state: str | None
    input_requests: dict[str, Any] | None
    last_result: dict[str, Any] | None
    final_text: str | None
    error: str | None
    confirm_drop: bool
    environment_tag: str
    had_hitl: bool


def _gateway_base_url() -> str:
    port = os.getenv("AGENTGATEWAY_PORT", "8080")
    return f"http://127.0.0.1:{port}"


def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
        model=os.getenv("MODEL_NAME", "qwen/qwen3.6-35b-a3b"),
        temperature=0,
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def call_model(state: AgentState) -> dict[str, Any]:
    cluster_id = state.get("cluster_id") or DEFAULT_CLUSTER_ID
    script_name = state.get("script_name") or DEFAULT_SCRIPT_NAME
    prompt = state.get("user_prompt") or (
        f"Apply emergency migration {script_name} on cluster {cluster_id}."
    )
    console.agent(
        "LLM acknowledging operator intent",
        f"model={os.getenv('MODEL_NAME', 'qwen/qwen3.6-35b-a3b')}",
        f"prompt: {prompt}",
    )
    llm = _build_llm()
    message = llm.invoke(
        [
            (
                "system",
                "You are a DevOps assistant. Briefly acknowledge the migration request "
                "in 1-2 sentences. Do not invent tool results.",
            ),
            ("human", prompt),
        ]
    )
    note = getattr(message, "content", str(message))
    note_str = note if isinstance(note, str) else str(note)
    console.agent("LLM response", note_str)
    return {
        "cluster_id": cluster_id,
        "script_name": script_name,
        "llm_note": note_str,
    }


def call_tool(state: AgentState) -> dict[str, Any]:
    console.trace(
        "LangGraph node: call_tool",
        "Invoking apply_db_migration through agentgateway (not direct to MCP).",
    )
    client = McpClient(_gateway_base_url(), verbose=True)
    try:
        result = client.call_apply_db_migration(
            cluster_id=state["cluster_id"],
            script_name=state["script_name"],
        )
    except McpClientError as exc:
        msg = f"Tool call failed: {exc}"
        console.err("tools/call failed", msg)
        return {"error": str(exc), "final_text": msg}
    except Exception as exc:  # noqa: BLE001
        msg = f"Tool call failed: {exc}"
        console.err("tools/call failed", msg)
        return {"error": str(exc), "final_text": msg}

    if result.get("resultType") == "input_required":
        return {
            "last_result": result,
            "request_state": result.get("requestState"),
            "input_requests": result.get("inputRequests"),
            "error": None,
            "had_hitl": True,
        }

    text = McpClient.result_text(result)
    console.ok("Non-destructive path completed without HITL", text)
    return {
        "last_result": result,
        "final_text": text,
        "request_state": None,
        "input_requests": None,
        "error": None,
        "had_hitl": False,
    }


def route_after_tool(state: AgentState) -> Literal["human_input", "done"]:
    if state.get("error"):
        return "done"
    result = state.get("last_result") or {}
    if result.get("resultType") == "input_required":
        return "human_input"
    return "done"


def human_input(state: AgentState) -> dict[str, Any]:
    payload = {
        "message": "Human authorization required for destructive migration",
        "cluster_id": state.get("cluster_id"),
        "script_name": state.get("script_name"),
        "allowed_environment_tags": list(ENVIRONMENT_TAGS),
        "fields": ["confirm_drop", "environment_tag"],
        "input_requests": state.get("input_requests"),
    }
    answers = interrupt(payload)
    if not isinstance(answers, dict):
        answers = {}
    return {
        "confirm_drop": _as_bool(answers.get("confirm_drop")),
        "environment_tag": str(answers.get("environment_tag") or "").strip(),
        "had_hitl": True,
    }


def retry_tool(state: AgentState) -> dict[str, Any]:
    console.trace(
        "LangGraph node: retry_tool",
        "New HTTP POST (new JSON-RPC id) with echoed requestState + inputResponses.",
        "Any MCP replica behind the gateway can verify HMAC and continue.",
    )
    client = McpClient(_gateway_base_url(), verbose=True)
    request_state = state.get("request_state")
    if not request_state:
        msg = "Missing requestState for retry"
        console.err("MRTR retry aborted", msg)
        return {"error": msg, "final_text": msg}

    confirm_drop = bool(state.get("confirm_drop"))
    environment_tag = str(state.get("environment_tag") or "").strip()
    console.agent(
        "Packaging operator answers as inputResponses",
        f"confirm_drop={confirm_drop}",
        f"environment_tag={environment_tag!r}",
    )
    input_responses = McpClient.build_input_responses(
        confirm_drop=confirm_drop,
        environment_tag=environment_tag,
    )
    try:
        result = client.call_apply_db_migration(
            cluster_id=state["cluster_id"],
            script_name=state["script_name"],
            request_state=request_state,
            input_responses=input_responses,
        )
    except McpClientError as exc:
        msg = f"Retry failed (fail-closed or protocol error): {exc}"
        console.err("MRTR retry failed", msg)
        return {"error": str(exc), "final_text": msg, "last_result": None}
    except Exception as exc:  # noqa: BLE001
        msg = f"Retry failed: {exc}"
        console.err("MRTR retry failed", msg)
        return {"error": str(exc), "final_text": msg}

    text = McpClient.result_text(result)
    return {
        "last_result": result,
        "final_text": text,
        "error": None,
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("call_tool", call_tool)
    graph.add_node("human_input", human_input)
    graph.add_node("retry_tool", retry_tool)
    graph.add_edge(START, "call_model")
    graph.add_edge("call_model", "call_tool")
    graph.add_conditional_edges(
        "call_tool",
        route_after_tool,
        {"human_input": "human_input", "done": END},
    )
    graph.add_edge("human_input", "retry_tool")
    graph.add_edge("retry_tool", END)
    return graph.compile(checkpointer=MemorySaver())


def prompt_terminal_for_answers(interrupt_value: Any) -> dict[str, Any]:
    console.hitl_prompt(interrupt_value)
    confirm_raw = input(_c_prompt("confirm_drop [true/false]: ")).strip().lower()
    confirm_drop = confirm_raw in {"1", "true", "yes", "y"}
    environment_tag = input(
        _c_prompt(f"environment_tag {list(ENVIRONMENT_TAGS)}: ")
    ).strip()
    console.agent(
        "Operator answers captured",
        f"confirm_drop={confirm_drop}",
        f"environment_tag={environment_tag!r}",
    )
    return {"confirm_drop": confirm_drop, "environment_tag": environment_tag}


def _c_prompt(label: str) -> str:
    # Keep prompts readable even without color helpers imported here.
    return f"\n  {label}"


def run_migration_agent(
    *,
    cluster_id: str = DEFAULT_CLUSTER_ID,
    script_name: str = DEFAULT_SCRIPT_NAME,
    user_prompt: str | None = None,
    thread_id: str = "mrtr-demo",
) -> dict[str, Any]:
    gateway = _gateway_base_url()
    console.intro_banner(
        cluster_id=cluster_id,
        script_name=script_name,
        gateway=gateway,
    )
    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial: AgentState = {
        "cluster_id": cluster_id,
        "script_name": script_name,
        "user_prompt": user_prompt
        or f"Apply emergency migration {script_name} on cluster {cluster_id}.",
        "had_hitl": False,
    }

    result = app.invoke(initial, config)
    while True:
        state = app.get_state(config)
        if not state.next:
            break
        interrupt_value = None
        if isinstance(result, dict) and result.get("__interrupt__"):
            first = result["__interrupt__"][0]
            interrupt_value = getattr(first, "value", first)
        if interrupt_value is None:
            interrupt_value = {
                "cluster_id": cluster_id,
                "script_name": script_name,
                "allowed_environment_tags": list(ENVIRONMENT_TAGS),
            }
        answers = prompt_terminal_for_answers(interrupt_value)
        result = app.invoke(Command(resume=answers), config)

    final_state = dict(app.get_state(config).values)
    final_text = final_state.get("final_text") or final_state.get("error") or "No result"
    console.summary(
        final_text=str(final_text),
        llm_note=final_state.get("llm_note"),
        had_hitl=bool(final_state.get("had_hitl")),
    )
    return final_state
