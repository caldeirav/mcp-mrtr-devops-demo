#!/usr/bin/env python3
"""CLI orchestrator: validate LLM, start MCP + agentgateway, run MRTR HITL demo."""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
GATEWAY_CONFIG = ROOT / "agentgateway.yaml"
CONTRACT_GATEWAY = ROOT / "specs" / "001-mrtr-db-migration" / "contracts" / "agentgateway.yaml"

_CHILDREN: list[subprocess.Popen[Any]] = []


def _cleanup() -> None:
    for proc in reversed(_CHILDREN):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _require_env() -> dict[str, str]:
    required = [
        "OPENAI_API_BASE",
        "OPENAI_API_KEY",
        "MODEL_NAME",
        "AGENTGATEWAY_PORT",
        "MCP_SERVER_PORT",
        "MCP_HMAC_SECRET",
    ]
    missing = [key for key in required if not os.getenv(key, "").strip()]
    if missing:
        print(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\nCopy .env.example to .env and fill values.",
            file=sys.stderr,
        )
        sys.exit(1)
    return {key: os.environ[key].strip() for key in required}


def validate_llm(base_url: str, api_key: str) -> None:
    url = base_url.rstrip("/") + "/models"
    print(f"Validating LM Studio at {url} ...")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(
            "FAIL: Local language-model endpoint is unreachable.\n"
            f"  Tried: {url}\n"
            f"  Error: {exc}\n"
            "Start LM Studio (OpenAI-compatible server) and reload the model, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("LM Studio connectivity OK.")


def ensure_gateway_config() -> None:
    if GATEWAY_CONFIG.exists():
        return
    if CONTRACT_GATEWAY.exists():
        GATEWAY_CONFIG.write_text(CONTRACT_GATEWAY.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {GATEWAY_CONFIG} from contracts/")
        return
    GATEWAY_CONFIG.write_text(
        """# yaml-language-server: $schema=https://agentgateway.dev/schema/config
mcp:
  port: 8080
  statefulMode: stateless
  targets:
    - name: devops-migration
      mcp:
        host: http://127.0.0.1:8000/mcp
""",
        encoding="utf-8",
    )
    print(f"Wrote default {GATEWAY_CONFIG}")


def wait_for_port(url: str, *, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=1.0) as client:
                client.get(url)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def start_mcp_server(port: str) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mcp_server.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            port,
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT),
        env=env,
    )
    _CHILDREN.append(proc)
    wait_for_port(f"http://127.0.0.1:{port}/healthz")
    print(f"MCP server listening on :{port}")
    return proc


def start_agentgateway() -> subprocess.Popen[Any]:
    binary = shutil.which("agentgateway")
    if not binary:
        print(
            "FAIL: `agentgateway` binary not found on PATH.\n"
            "Install from https://agentgateway.dev/docs/standalone/latest/deployment/binary\n"
            "Demo tool calls must route through agentgateway (constitution).",
            file=sys.stderr,
        )
        sys.exit(1)
    proc = subprocess.Popen(
        [binary, "-f", str(GATEWAY_CONFIG)],
        cwd=str(ROOT),
    )
    _CHILDREN.append(proc)
    port = os.getenv("AGENTGATEWAY_PORT", "8080")
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("agentgateway exited early; check config and ports")
        try:
            with httpx.Client(timeout=1.0) as client:
                client.post(f"http://127.0.0.1:{port}/mcp", json={})
            break
        except httpx.ConnectError:
            time.sleep(0.25)
            continue
        except Exception:
            break
    else:
        raise RuntimeError("Timed out waiting for agentgateway")
    print(f"agentgateway listening on :{port} (statefulMode: stateless)")
    return proc


def main() -> None:
    load_dotenv(ROOT / ".env")
    env = _require_env()
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    validate_llm(env["OPENAI_API_BASE"], env["OPENAI_API_KEY"])
    ensure_gateway_config()

    start_mcp_server(env["MCP_SERVER_PORT"])
    start_agentgateway()

    from agent.graph import run_migration_agent
    from mcp_server.mrtr_types import DEFAULT_CLUSTER_ID, DEFAULT_SCRIPT_NAME

    print(
        f"\nStarting MRTR demo: cluster={DEFAULT_CLUSTER_ID} "
        f"script={DEFAULT_SCRIPT_NAME}\n"
    )
    run_migration_agent(
        cluster_id=DEFAULT_CLUSTER_ID,
        script_name=DEFAULT_SCRIPT_NAME,
    )


if __name__ == "__main__":
    main()
