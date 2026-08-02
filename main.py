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
from typing import Any, IO, TextIO

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
GATEWAY_CONFIG = ROOT / "agentgateway.yaml"
CONTRACT_GATEWAY = (
    ROOT / "specs" / "002-gateway-llm-tracing" / "contracts" / "agentgateway.yaml"
)
LOG_DIR = ROOT / ".demo_logs"
JAEGER_CONTAINER = "jaeger"
JAEGER_IMAGE = "jaegertracing/all-in-one:latest"

_CHILDREN: list[subprocess.Popen[Any]] = []
_LOG_HANDLES: list[IO[Any]] = []
# Only stop Jaeger on exit if this harness created/started it for the run.
_JAEGER_STARTED_BY_HARNESS = False
_CONTAINER_CLI: str | None = None


def resolve_container_cli() -> str | None:
    """Return podman or docker binary path.

    Order:
    1. ``CONTAINER_RUNTIME`` env (``podman`` | ``docker`` | absolute path)
    2. Prefer ``podman`` on PATH, then ``docker`` (Podman-first for this demo)
    """
    preferred = (os.getenv("CONTAINER_RUNTIME") or "").strip()
    if preferred:
        if preferred in {"podman", "docker"}:
            return shutil.which(preferred)
        # Absolute or bare command name
        if os.path.isabs(preferred) and os.access(preferred, os.X_OK):
            return preferred
        return shutil.which(preferred)
    return shutil.which("podman") or shutil.which("docker")


def _cleanup() -> None:
    global _JAEGER_STARTED_BY_HARNESS, _CONTAINER_CLI
    for proc in reversed(_CHILDREN):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    for handle in _LOG_HANDLES:
        try:
            handle.close()
        except Exception:  # noqa: BLE001
            pass
    # Do not rm the container — preserve a presenter’s pre-existing Jaeger data.
    # Only stop a container this harness started for the current run.
    if _JAEGER_STARTED_BY_HARNESS and _CONTAINER_CLI:
        subprocess.run(
            [_CONTAINER_CLI, "stop", JAEGER_CONTAINER],
            check=False,
            capture_output=True,
        )
        _JAEGER_STARTED_BY_HARNESS = False


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


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def validate_llm(base_url: str, api_key: str) -> None:
    from agent import console

    url = base_url.rstrip("/") + "/models"
    console.trace("Validating LM Studio", f"GET {url}")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        console.err(
            "LM Studio unreachable",
            f"Tried: {url}",
            f"Error: {exc}",
            "Start LM Studio (OpenAI-compatible server) and load the model, then retry.",
        )
        sys.exit(1)
    console.ok("LM Studio connectivity OK", f"base={base_url}")


def ensure_gateway_config() -> None:
    from agent import console

    if GATEWAY_CONFIG.exists():
        console.trace(
            "agentgateway.yaml present",
            f"path={GATEWAY_CONFIG}",
            "Must keep statefulMode: stateless (no Mcp-Session-Id pinning)",
            "Expect llm → LM Studio and frontendPolicies.tracing → :4317",
        )
        return
    if CONTRACT_GATEWAY.exists():
        GATEWAY_CONFIG.write_text(CONTRACT_GATEWAY.read_text(encoding="utf-8"), encoding="utf-8")
        console.trace("Wrote agentgateway.yaml from specs/002-gateway-llm-tracing/contracts/")
        return
    GATEWAY_CONFIG.write_text(
        """# yaml-language-server: $schema=https://agentgateway.dev/schema/config
frontendPolicies:
  tracing:
    host: localhost:4317
    randomSampling: true
llm:
  models:
  - name: "*"
    provider:
      custom:
        formats:
        - type: completions
    params:
      apiKey: $OPENAI_API_KEY
      model: qwen/qwen3.6-35b-a3b
      baseUrl: http://127.0.0.1:1234/v1
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
    console.trace("Wrote default agentgateway.yaml")


def maybe_start_jaeger() -> None:
    """Start or reuse Jaeger when ENABLE_JAEGER=1. Never fail the HITL demo.

    Uses Podman by default when available; Docker otherwise. Override with
    ``CONTAINER_RUNTIME=podman|docker``.
    """
    global _JAEGER_STARTED_BY_HARNESS, _CONTAINER_CLI
    from agent import console

    if not _truthy(os.getenv("ENABLE_JAEGER")):
        console.trace(
            "Jaeger skipped",
            "ENABLE_JAEGER unset/0 — HITL demo continues without traces",
            "Set ENABLE_JAEGER=1 (uses podman if available, else docker), or:",
            "podman run -d --name jaeger -p 16686:16686 -p 4317:4317 "
            f"{JAEGER_IMAGE}",
        )
        return

    cli = resolve_container_cli()
    if not cli:
        console.warn(
            "ENABLE_JAEGER=1 but neither podman nor docker is on PATH",
            "Install Podman (or Docker), ensure the engine is running "
            "(e.g. podman machine start), then retry",
            "Traces will be empty; continuing with MCP + agentgateway HITL demo",
        )
        return

    cli_name = Path(cli).name
    _CONTAINER_CLI = cli

    # Fail soft if the engine/VM is not running (common with Podman Desktop).
    info = subprocess.run(
        [cli, "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if info.returncode != 0:
        console.warn(
            f"ENABLE_JAEGER=1 but {cli_name} engine is not ready",
            (info.stderr or info.stdout or "").strip()[:400],
            "Try: podman machine start   (or start Podman Desktop / Docker Desktop)",
            "Continuing without traces",
        )
        return

    inspect = subprocess.run(
        [cli, "inspect", "-f", "{{.State.Running}}", JAEGER_CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode == 0:
        running = inspect.stdout.strip().lower() == "true"
        if running:
            console.ok(
                "Jaeger already running",
                f"runtime={cli_name}",
                "UI http://localhost:16686",
                "OTLP gRPC localhost:4317",
            )
            return
        start = subprocess.run(
            [cli, "start", JAEGER_CONTAINER],
            capture_output=True,
            text=True,
            check=False,
        )
        if start.returncode == 0:
            _JAEGER_STARTED_BY_HARNESS = True
            console.ok(
                "Started existing Jaeger container",
                f"runtime={cli_name}",
                "UI http://localhost:16686",
                f"Harness will `{cli_name} stop` (not rm) this container on exit",
            )
            return
        console.warn(
            "Failed to start existing Jaeger container",
            start.stderr.strip() or start.stdout.strip(),
            "Continuing without traces",
        )
        return

    run = subprocess.run(
        [
            cli,
            "run",
            "-d",
            "--name",
            JAEGER_CONTAINER,
            "-p",
            "16686:16686",
            "-p",
            "4317:4317",
            JAEGER_IMAGE,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode == 0:
        _JAEGER_STARTED_BY_HARNESS = True
        console.ok(
            "Jaeger started",
            f"runtime={cli_name}",
            f"image={JAEGER_IMAGE}",
            "UI http://localhost:16686",
            "OTLP gRPC localhost:4317",
            f"Harness will `{cli_name} stop` (not rm) this container on exit",
        )
        return

    console.warn(
        "Could not start Jaeger",
        run.stderr.strip() or run.stdout.strip(),
        "HITL demo continues; traces will not appear until OTLP :4317 is up",
    )


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


def _open_log(name: str) -> TextIO:
    LOG_DIR.mkdir(exist_ok=True)
    handle = open(LOG_DIR / name, "w", encoding="utf-8")  # noqa: SIM115
    _LOG_HANDLES.append(handle)
    return handle


def start_mcp_server(port: str) -> subprocess.Popen[Any]:
    from agent import console

    env = os.environ.copy()
    log = _open_log("mcp_server.log")
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
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    _CHILDREN.append(proc)
    wait_for_port(f"http://127.0.0.1:{port}/healthz")
    console.trace(
        "MCP server ready",
        f"http://127.0.0.1:{port}/mcp",
        f"logs → {LOG_DIR / 'mcp_server.log'}",
    )
    return proc


def start_agentgateway() -> subprocess.Popen[Any]:
    from agent import console

    binary = shutil.which("agentgateway")
    if not binary:
        console.err(
            "agentgateway not found on PATH",
            "Install: curl -sL https://agentgateway.dev/install | bash",
            "Demo tool calls must route through agentgateway (constitution).",
        )
        sys.exit(1)
    log = _open_log("agentgateway.log")
    # Pass through OPENAI_API_KEY so agentgateway can expand $OPENAI_API_KEY for llm.params.
    env = os.environ.copy()
    if not env.get("OPENAI_API_KEY", "").strip():
        env["OPENAI_API_KEY"] = "lm-studio"
    proc = subprocess.Popen(
        [binary, "-f", str(GATEWAY_CONFIG)],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    _CHILDREN.append(proc)
    port = os.getenv("AGENTGATEWAY_PORT", "8080")
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"agentgateway exited early; see {LOG_DIR / 'agentgateway.log'}"
            )
        try:
            with httpx.Client(timeout=1.0) as client:
                client.post(
                    f"http://127.0.0.1:{port}/mcp",
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                    json={},
                )
            break
        except httpx.ConnectError:
            time.sleep(0.25)
            continue
        except Exception:
            break
    else:
        raise RuntimeError("Timed out waiting for agentgateway")
    console.trace(
        "agentgateway ready (statefulMode=stateless)",
        f"http://127.0.0.1:{port}/mcp",
        "Admin UI http://localhost:15000/ui/ (LLM playground → LM Studio)",
        "★ No Mcp-Session-Id pinning — retries can hit any backend instance",
        f"logs → {LOG_DIR / 'agentgateway.log'}",
    )
    return proc


def main() -> None:
    load_dotenv(ROOT / ".env")
    env = _require_env()
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    validate_llm(env["OPENAI_API_BASE"], env["OPENAI_API_KEY"])
    ensure_gateway_config()
    maybe_start_jaeger()

    start_mcp_server(env["MCP_SERVER_PORT"])
    start_agentgateway()

    from agent.graph import run_migration_agent
    from mcp_server.mrtr_types import DEFAULT_CLUSTER_ID, DEFAULT_SCRIPT_NAME

    run_migration_agent(
        cluster_id=DEFAULT_CLUSTER_ID,
        script_name=DEFAULT_SCRIPT_NAME,
    )


if __name__ == "__main__":
    main()
