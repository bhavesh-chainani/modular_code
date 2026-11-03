"""Trace shape: observation names and types are what dashboards and evaluators filter on, so pin them."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from modkit import extract, send_email
from modkit.config import Settings
from modkit.observability import child_of, langflow_span, llm_usage

_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="session")
def langfuse_client():
    from langfuse import Langfuse

    # Capture spans synchronously in memory via the tracer provider (works on SDK 3.x and 5.x).
    # Langfuse's own batch export to the unreachable host fails in the background.
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    client = Langfuse(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        base_url="http://127.0.0.1:9",
        tracer_provider=provider,
        timeout=1,
    )
    yield client
    client.shutdown()


@pytest.fixture
def spans(langfuse_client, monkeypatch):
    """Turn tracing on; call the returned function to get the finished spans, keyed by name."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    _EXPORTER.clear()

    def finished() -> dict:
        result: dict = {}
        for span in _EXPORTER.get_finished_spans():
            result.setdefault(span.name, []).append(span)
        return result

    return finished


def attr(span, key: str):
    """A langfuse.observation.* attribute, JSON-decoded where the SDK encodes it (metadata.<key>, input, ...)."""
    value = span.attributes.get(f"langfuse.observation.{key}")
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def test_extract_trace_shape(spans, llm, tmp_path):
    f = tmp_path / "invoice.txt"
    f.write_text("Invoice from Acme, total $42")
    llm.replies.append('{"vendor": "Acme"}')

    extract(f, "Extract invoice details", fields=["vendor"], model="ollama/llama3.1")

    s = spans()
    root, load, chain, gen = (s[n][0] for n in ("extract-data", "load-document", "generate-structured-output", "generate-completion"))
    assert [attr(x, "type") for x in (root, load, chain, gen)] == ["span", "retriever", "chain", "generation"]
    assert root.parent is None
    assert load.parent.span_id == chain.parent.span_id == root.context.span_id
    assert gen.parent.span_id == chain.context.span_id
    assert attr(root, "input")["instructions"] == "Extract invoice details"
    assert attr(root, "output") == {"vendor": "Acme"}
    assert attr(gen, "input")[-1]["role"] == "user"  # OpenAI-style messages, not raw function args
    assert attr(gen, "output") == {"role": "assistant", "content": '{"vendor": "Acme"}'}
    assert attr(gen, "model.name") == "ollama/llama3.1"
    assert attr(gen, "usage_details") == {"input": 10, "output": 5}


def test_raw_text_source_skips_retriever(spans, llm):
    llm.replies.append('{"summary": "short"}')
    extract("some text", "Summarise")
    assert "load-document" not in spans()


def test_structured_retry_is_flagged(spans, llm):
    llm.replies.extend(["not json", '{"a": 1}'])
    extract("some text", "x")
    s = spans()
    chain = s["generate-structured-output"][0]
    assert len(s["generate-completion"]) == 2
    assert attr(chain, "level") == "WARNING"
    assert attr(chain, "metadata.attempts") == 2


def test_email_is_a_tool_and_errors_are_recorded(spans):
    with pytest.raises(ValueError):
        send_email(" , ", "s", "b", settings=Settings())
    span = spans()["send-email"][0]
    assert attr(span, "type") == "tool"
    assert attr(span, "level") == "ERROR"
    assert "no recipients" in attr(span, "status_message")


def test_child_of_joins_an_existing_trace(spans, llm):
    llm.replies.append('{"a": 1}')
    trace_id, span_id = "ab" * 16, "cd" * 8
    with child_of(trace_id, span_id):
        extract("some text", "x")
    root = spans()["extract-data"][0]
    assert format(root.context.trace_id, "032x") == trace_id
    assert format(root.parent.span_id, "016x") == span_id


def test_mcp_tools_tag_their_traces(spans, llm):
    from modkit.mcp_server import mcp

    llm.replies.append("hi")
    asyncio.run(mcp.call_tool("ask_llm", {"prompt": "hello"}))
    gen = spans()["generate-completion"][0]
    assert list(gen.attributes["langfuse.trace.tags"]) == ["mcp"]


def test_llm_usage_splits_cache_tokens_and_prefers_proxy_cost():
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=60),
            cache_creation_input_tokens=30,
        ),
        _hidden_params={"response_cost": 0.002},
    )
    assert llm_usage(response) == {
        "usage_details": {"input": 10, "output": 20, "cache_read_input_tokens": 60, "cache_creation_input_tokens": 30},
        "cost_details": {"total": 0.002},
    }


def test_llm_usage_leaves_unknown_cost_to_langfuse():
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), _hidden_params={"response_cost": 0.0}
    )
    assert "cost_details" not in llm_usage(response)


def test_langflow_span_prefers_component_span(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    root, own = SimpleNamespace(id="root"), SimpleNamespace(id="own")
    tracer = SimpleNamespace(ready=True, spans={"v1": own}, _root_span=root, langfuse_trace_id="t")
    component = SimpleNamespace(
        tracing_service=SimpleNamespace(get_tracer=lambda name: tracer),
        get_vertex=lambda: SimpleNamespace(id="v1"),
    )
    assert langflow_span(component) == ("t", "own")
    tracer.spans = {}
    assert langflow_span(component) == ("t", "root")
    assert langflow_span(object()) == (None, None)  # not a Langflow component: fall back, don't fail
