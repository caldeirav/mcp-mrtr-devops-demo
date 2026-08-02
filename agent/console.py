"""Terminal presentation for the MRTR / SEP-2322 demo.

Separates:
  TRACE  — infrastructure / protocol execution
  AGENT  — LLM narrative
  HITL   — operator prompts
  SEP    — what changed vs pre-2026 sticky-SSE MCP
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def _use_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    WHITE = "\033[97m"


def _c(code: str, text: str) -> str:
    if not _use_color():
        return text
    return f"{code}{text}{_C.RESET}"


def _rule(char: str = "─", width: int = 78) -> str:
    return char * width


def _banner(kind: str, title: str) -> None:
    styles = {
        "TRACE": (_C.CYAN, "TRACE"),
        "AGENT": (_C.GREEN, "AGENT"),
        "HITL": (_C.YELLOW, "HITL "),
        "SEP": (_C.MAGENTA, "SEP  "),
        "OK": (_C.GREEN, " OK  "),
        "WARN": (_C.YELLOW, "WARN "),
        "ERR": (_C.RED, " ERR "),
    }
    color, label = styles.get(kind, (_C.WHITE, kind[:5]))
    print()
    print(_c(color + _C.BOLD, f"┌{_rule('─', 10)} {label} · {title} {_rule('─', max(8, 50 - len(title)))}"))


def _end() -> None:
    print(_c(_C.DIM, f"└{_rule('─', 76)}"))


def _line(text: str = "", *, dim: bool = False) -> None:
    prefix = _c(_C.DIM, "│ ")
    body = _c(_C.DIM, text) if dim else text
    print(f"{prefix}{body}")


def intro_banner(*, cluster_id: str, script_name: str, gateway: str) -> None:
    print()
    print(_c(_C.BOLD + _C.MAGENTA, "╔" + "═" * 76 + "╗"))
    print(
        _c(
            _C.BOLD + _C.MAGENTA,
            "║  MCP SEP-2322 MRTR Demo — Stateless Human-in-the-Loop Migration Agent"
            + " " * 4
            + "║",
        )
    )
    print(_c(_C.BOLD + _C.MAGENTA, "╚" + "═" * 76 + "╝"))
    _banner("SEP", "What this demo proves (2026-07-28 vs legacy)")
    _line("Legacy (e.g. 2025-11-25): sticky SSE GET + server-held paused thread + Mcp-Session-Id")
    _line("SEP-2322 / 2026-07-28:")
    _line("  ★ resultType: input_required | complete   (required on every tool result)")
    _line("  ★ requestState HMAC continuation         (no server session store)")
    _line("  ★ inputRequests / inputResponses         (elicitation without open stream)")
    _line("  ★ per-request _meta                      (replaces initialize handshake)")
    _line("  ★ Mcp-Method / Mcp-Name headers          (L7 routing without body parse)")
    _line("  ✕ Mcp-Session-Id NOT used                (unpinned load balancing OK)")
    _line("  ✕ No persistent SSE GET for HITL pause   (HTTP call ends after yield)")
    _line()
    _line(f"Scenario: cluster={cluster_id}  script={script_name}")
    _line(f"Path:     LangGraph → agentgateway {gateway} → MCP server")
    _end()


def trace(title: str, *lines: str) -> None:
    _banner("TRACE", title)
    for line in lines:
        _line(line)
    _end()


def agent(title: str, *lines: str) -> None:
    _banner("AGENT", title)
    for line in lines:
        _line(line)
    _end()


def hitl_prompt(interrupt_value: Any) -> None:
    _banner("HITL", "Operator authorization (connection already closed — SEP-2322)")
    _line(_c(_C.BOLD, "The MCP HTTP round-trip ended with resultType=input_required."))
    _line("No sticky SSE socket is held open. State lives only in requestState.")
    _line()
    if isinstance(interrupt_value, dict):
        _line(str(interrupt_value.get("message", "")))
        _line(f"cluster_id:              {interrupt_value.get('cluster_id')}")
        _line(f"script_name:             {interrupt_value.get('script_name')}")
        _line(f"allowed environment_tag: {interrupt_value.get('allowed_environment_tags')}")
    _line()
    _line(_c(_C.YELLOW + _C.BOLD, "→ Your answers become inputResponses on the NEXT independent HTTP POST"))
    _end()


def ok(title: str, *lines: str) -> None:
    _banner("OK", title)
    for line in lines:
        _line(line)
    _end()


def warn(title: str, *lines: str) -> None:
    _banner("WARN", title)
    for line in lines:
        _line(line)
    _end()


def err(title: str, *lines: str) -> None:
    _banner("ERR", title)
    for line in lines:
        _line(line)
    _end()


def _truncate(value: str, limit: int = 64) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def annotate_headers(headers: dict[str, str]) -> None:
    _banner("SEP", "Outbound HTTP headers — what changed")
    rows = [
        ("Accept", headers.get("Accept", ""), "Streamable HTTP: must allow JSON + SSE"),
        (
            "MCP-Protocol-Version",
            headers.get("MCP-Protocol-Version", ""),
            "★ NEW — version on every request (no initialize)",
        ),
        (
            "Mcp-Method",
            headers.get("Mcp-Method", ""),
            "★ NEW (SEP-2243) — gateway routes without parsing body",
        ),
        (
            "Mcp-Name",
            headers.get("Mcp-Name", ""),
            "★ NEW (SEP-2243) — tool name for L7 policy / metering",
        ),
        (
            "Mcp-Session-Id",
            "(absent)",
            "✕ REMOVED in 2026-07-28 — sticky sessions prohibited here",
        ),
        ("Content-Type", headers.get("Content-Type", ""), "JSON-RPC body"),
    ]
    for name, value, note in rows:
        star = "★" if "NEW" in note or "REMOVED" in note else "·"
        _line(f"{star} {name}: {value}")
        _line(f"    {note}", dim=True)
    _end()


def annotate_request_body(payload: dict[str, Any], *, phase: str) -> None:
    title = (
        "Round-trip #1 tools/call (initial)"
        if phase == "initial"
        else "Round-trip #2 tools/call (MRTR retry — independent HTTP request)"
    )
    _banner("SEP", title)
    params = payload.get("params") or {}
    meta = params.get("_meta") or {}
    _line(f'jsonrpc id: {payload.get("id")}  method: {payload.get("method")}')
    _line()
    _line(_c(_C.BOLD, "params._meta  ★ NEW in 2026-07-28 (replaces initialize handshake):"))
    for key in (
        "io.modelcontextprotocol/protocolVersion",
        "io.modelcontextprotocol/clientInfo",
        "io.modelcontextprotocol/clientCapabilities",
    ):
        _line(f"  ★ {key}: {json.dumps(meta.get(key), ensure_ascii=False)}")
    _line()
    _line("params.arguments:")
    _line(f"  {_pretty(params.get('arguments') or {})}")
    if phase == "retry":
        _line()
        rs = params.get("requestState", "")
        _line(_c(_C.BOLD, "params.requestState  ★ NEW (SEP-2322 MRTR continuation handle):"))
        _line(f"  {_truncate(str(rs), 72)}  ({len(str(rs))} chars, HMAC-protected)")
        _line("  Client echoes opaque token unmodified — does NOT parse it.", dim=True)
        _line()
        _line(_c(_C.BOLD, "params.inputResponses  ★ NEW (SEP-2322 answers keyed to inputRequests):"))
        _line(f"  {_pretty(params.get('inputResponses') or {})}")
    else:
        _line()
        _line("params.requestState:     (absent on first call)", dim=True)
        _line("params.inputResponses:   (absent on first call)", dim=True)
    _line()
    _line(_c(_C.DIM, "Full JSON-RPC body:"))
    for line in _pretty(payload).splitlines():
        _line(line, dim=True)
    _end()


def annotate_response(result: dict[str, Any], *, http_status: int, content_type: str) -> None:
    result_type = result.get("resultType")
    _banner("SEP", f"Inbound tool result — resultType={result_type!r}")
    _line(f"HTTP {http_status}  Content-Type: {content_type}")
    _line()
    if result_type == "input_required":
        _line(_c(_C.BOLD + _C.MAGENTA, "★ resultType: \"input_required\"  — SEP-2322 yield (not an error)"))
        _line("  Legacy alternative: hold SSE GET + paused server thread until user answers.")
        _line("  Now: return 200, close the request, continue later with requestState.")
        _line()
        _line("inputRequests  ★ NEW:")
        _line(f"  {_pretty(result.get('inputRequests') or {})}")
        _line()
        rs = str(result.get("requestState") or "")
        _line("requestState  ★ NEW (server-minted HMAC continuation):")
        _line(f"  {_truncate(rs, 72)}  ({len(rs)} chars)")
        _line("  Socket can drop; any replica can resume after verifying HMAC.", dim=True)
    elif result_type == "complete":
        _line(_c(_C.BOLD + _C.GREEN, '★ resultType: "complete"  — terminal MRTR outcome'))
        _line(f"  content: {result.get('content')}")
    else:
        _line(f"result: {_pretty(result)}")
    _line()
    _line(_c(_C.DIM, "Full result object:"))
    for line in _pretty(result).splitlines():
        _line(line, dim=True)
    _end()


def sep_contrast_after_yield() -> None:
    _banner("SEP", "Moment of yield — legacy vs SEP-2322")
    _line(_c(_C.RED, "LEGACY:"))
    _line("  • Keep SSE GET open while waiting for human")
    _line("  • Pin client to one pod via Mcp-Session-Id")
    _line("  • If LB idle-timeout / scale-in → paused thread dies → restart demo")
    _line()
    _line(_c(_C.GREEN, "SEP-2322 (this demo):"))
    _line("  • HTTP response finished (resultType=input_required)")
    _line("  • Continuity = requestState only (HMAC, TTL, cluster/script bind)")
    _line("  • Retry is a NEW JSON-RPC id through agentgateway (statelessMode)")
    _line("  • Operator can take their time; no open socket required")
    _end()


def summary(*, final_text: str, llm_note: str | None, had_hitl: bool) -> None:
    _banner("OK", "Demo complete")
    if llm_note:
        _line(_c(_C.GREEN, "Agent (LLM):"))
        _line(f"  {llm_note}")
        _line()
    _line(_c(_C.BOLD, "Outcome:"))
    _line(f"  {final_text}")
    _line()
    if had_hitl:
        _line("You exercised a full MRTR loop:")
        _line("  1) tools/call → input_required + requestState")
        _line("  2) HITL (no sticky session)")
        _line("  3) tools/call retry + inputResponses + echoed requestState → complete")
    _end()
    print()
