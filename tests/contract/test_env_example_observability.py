from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"


def test_env_example_documents_observability_and_llm():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "ENABLE_JAEGER" in text
    assert "CONTAINER_RUNTIME" in text
    assert "podman" in text.lower()
    assert "OPENAI_API_BASE" in text
    assert "MODEL_NAME" in text
    assert "15000" in text
    assert "16686" in text
    assert "4317" in text
