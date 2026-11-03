"""Langfuse tracing for modkit modules.

Tracing is active only when LANGFUSE_PUBLIC_KEY is set (and LANGFUSE_TRACING_ENABLED isn't "false");
otherwise every helper here is a no-op, so modules work the same in tests, notebooks and
un-instrumented deployments. The check runs on every call, so keys loaded after import still count.
Give each client its own Langfuse project (its own keys) to keep traces separated, and set
LANGFUSE_TRACING_ENVIRONMENT (production / staging / development) to keep test runs apart.

Works with Langfuse SDK 3.15 (what the Langflow image pins) and 5.x. Prefer `observation()` over
`langfuse.observe` + `update_current_span()`: on SDK 3.x the latter resets typed observations
(tool, retriever, ...) to plain spans.
"""

import os
from contextlib import contextmanager, nullcontext
from typing import Any


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and (
        os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() != "false"
    )


class _NoopObservation:
    def update(self, **_: Any) -> "_NoopObservation":
        return self


@contextmanager
def observation(name: str, *, as_type: str = "span", **fields: Any):
    """Open a Langfuse observation as the current one and yield it, so the body can `.update()` it.

    `fields` are the start attributes (input, metadata, model, model_parameters, ...). Name it like
    an API, verb first (`extract-data`), with no ids or model names in it. Exceptions mark the
    observation as ERROR and propagate.
    """
    if not tracing_enabled():
        yield _NoopObservation()
        return
    from langfuse import get_client

    with get_client().start_as_current_observation(name=name, as_type=as_type, **fields) as obs:
        try:
            yield obs
        except Exception as e:
            obs.update(level="ERROR", status_message=f"{type(e).__name__}: {e}")
            raise


def trace_attributes(**attributes: Any):
    """Tags / metadata / user_id / session_id for every observation opened inside (propagate_attributes)."""
    if not tracing_enabled():
        return nullcontext()
    from langfuse import propagate_attributes

    return propagate_attributes(**attributes)


@contextmanager
def child_of(trace_id: str | None, span_id: str | None):
    """Nest observations opened inside under an existing span, e.g. one from Langflow's own tracer."""
    if not (tracing_enabled() and trace_id and span_id):
        yield
        return
    from opentelemetry import trace

    parent = trace.NonRecordingSpan(
        trace.SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(span_id, 16),
            is_remote=True,
            trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED),
        )
    )
    with trace.use_span(parent):
        yield


def langflow_span(component: Any) -> tuple[str | None, str | None]:
    """(trace_id, span_id) of the Langfuse span Langflow opened for `component` (or the flow's root span).

    Pass the result to `child_of` so a flow run and the modkit calls it makes land in one trace.
    Duck-typed against Langflow's LangFuseTracer, the same internals Langflow uses for its LangChain
    callback; anything unexpected returns (None, None) and modkit traces stand alone instead.
    """
    try:
        tracer = component.tracing_service.get_tracer("langfuse")
        if tracer is None or not tracer.ready:
            return None, None
        vertex = component.get_vertex()
        span = (tracer.spans.get(vertex.id) if vertex is not None else None) or tracer._root_span
        return tracer.langfuse_trace_id, span.id
    except Exception:
        return None, None


def record_generation(generation: Any, response: Any) -> None:
    """Attach the reply, finish reason, token usage and cost from a LiteLLM response to `generation`."""
    if not tracing_enabled():
        return
    choice = response.choices[0]
    output = {"role": "assistant", "content": choice.message.content or ""}
    if reasoning := getattr(choice.message, "reasoning_content", None):
        output["reasoning_content"] = reasoning
    metadata = {"finish_reason": getattr(choice, "finish_reason", None)}
    headers = (getattr(response, "_hidden_params", None) or {}).get("additional_headers") or {}
    if resolved := headers.get("llm_provider-x-litellm-model-name"):
        metadata["resolved_model"] = resolved  # what a LiteLLM proxy alias routed to
    generation.update(output=output, metadata=metadata, **llm_usage(response))


def llm_usage(response: Any) -> dict:
    """usage_details and cost_details for a LiteLLM response, ready for `generation.update(**...)`.

    Langfuse usage buckets must not overlap, but LiteLLM's prompt_tokens include cache reads and
    writes, so those are split out of `input`. Cost comes from the LiteLLM proxy when present
    (it prices the proxy's own model aliases), else from LiteLLM's price list. A zero cost means
    "unknown model", so it is left out and Langfuse can infer cost from its own model table.
    """
    details: dict = {}
    usage = getattr(response, "usage", None)
    if usage is not None:
        cache_read = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", None) or 0
        usage_details = {
            "input": usage.prompt_tokens - cache_read - cache_write,
            "output": usage.completion_tokens,
        }
        if cache_read:
            usage_details["cache_read_input_tokens"] = cache_read
        if cache_write:
            usage_details["cache_creation_input_tokens"] = cache_write
        details["usage_details"] = usage_details

    cost = (getattr(response, "_hidden_params", None) or {}).get("response_cost")
    if cost is None:
        import litellm

        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:  # unknown model pricing shouldn't break the call
            cost = None
    if cost:
        details["cost_details"] = {"total": float(cost)}
    return details
