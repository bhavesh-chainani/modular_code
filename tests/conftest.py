from types import SimpleNamespace

import pytest


def fake_response(content: str):
    """Minimal stand-in for a LiteLLM ModelResponse."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)


@pytest.fixture
def llm(monkeypatch):
    """Queue canned replies for litellm.completion and record every call."""
    replies: list[str] = []
    calls: list[dict] = []

    def completion(**kwargs):
        calls.append(kwargs)
        return fake_response(replies.pop(0))

    monkeypatch.setattr("modkit.llm.client.litellm.completion", completion)
    return SimpleNamespace(replies=replies, calls=calls)
