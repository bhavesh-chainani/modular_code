import pytest
from pydantic import BaseModel, ValidationError

from modkit.llm import complete, structured


class Invoice(BaseModel):
    number: str
    total: float


def test_complete_uses_given_model_and_system(llm):
    llm.replies.append("hi")
    assert complete("hello", model="openai/gpt-5", system="be brief") == "hi"
    call = llm.calls[0]
    assert call["model"] == "openai/gpt-5"
    assert call["messages"][0] == {"role": "system", "content": "be brief"}


def test_complete_falls_back_to_default_model(llm):
    llm.replies.append("ok")
    complete("hello")
    assert llm.calls[0]["model"] == "anthropic/claude-sonnet-5-5"


def test_structured_strips_code_fences(llm):
    llm.replies.append('```json\n{"number": "A1", "total": 9.5}\n```')
    assert structured("x", Invoice) == Invoice(number="A1", total=9.5)


def test_structured_retries_on_invalid_json(llm):
    llm.replies.extend(["not json", '{"number": "A1", "total": 1}'])
    assert structured("x", Invoice).number == "A1"
    assert "previous answer was invalid" in llm.calls[1]["messages"][-1]["content"]


def test_structured_raises_after_retries(llm):
    llm.replies.extend(["nope", "still nope"])
    with pytest.raises(ValidationError):
        structured("x", Invoice, retries=1)


def test_structured_without_schema_returns_dict(llm):
    llm.replies.append('{"anything": [1, 2]}')
    assert structured("x") == {"anything": [1, 2]}


def test_model_options_from_env(monkeypatch):
    from modkit.config import get_settings
    from modkit.llm import model_options

    monkeypatch.setenv("MODKIT_DEFAULT_MODEL", "openai.gpt-5")
    monkeypatch.setenv("MODKIT_MODEL_CHOICES", "vertex_ai.anthropic.claude-sonnet-5-5, openai.gpt-5")
    get_settings.cache_clear()
    try:
        assert model_options() == ["openai.gpt-5", "vertex_ai.anthropic.claude-sonnet-5-5"]
    finally:
        get_settings.cache_clear()
