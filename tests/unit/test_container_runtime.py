from main import resolve_container_cli


def test_resolve_prefers_podman_when_both_present(monkeypatch):
    monkeypatch.delenv("CONTAINER_RUNTIME", raising=False)

    def fake_which(name: str) -> str | None:
        return {"podman": "/opt/podman", "docker": "/opt/docker"}.get(name)

    monkeypatch.setattr("main.shutil.which", fake_which)
    assert resolve_container_cli() == "/opt/podman"


def test_resolve_falls_back_to_docker(monkeypatch):
    monkeypatch.delenv("CONTAINER_RUNTIME", raising=False)

    def fake_which(name: str) -> str | None:
        return {"docker": "/opt/docker"}.get(name)

    monkeypatch.setattr("main.shutil.which", fake_which)
    assert resolve_container_cli() == "/opt/docker"


def test_resolve_honors_container_runtime_env(monkeypatch):
    monkeypatch.setenv("CONTAINER_RUNTIME", "docker")

    def fake_which(name: str) -> str | None:
        return {"podman": "/opt/podman", "docker": "/opt/docker"}.get(name)

    monkeypatch.setattr("main.shutil.which", fake_which)
    assert resolve_container_cli() == "/opt/docker"
