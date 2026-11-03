"""Thin LiteLLM wrapper so every module can switch models by name (e.g. "openai/gpt-5", "ollama/llama3")."""

import json
import re
from typing import Any, TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from modkit.config import get_settings
from modkit.observability import observation, record_generation

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def complete(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.0,
    **kwargs: Any,
) -> str:
    """Single-turn completion. Extra kwargs are passed straight to litellm.completion."""
    model = model or get_settings().default_model
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    params = {"temperature": temperature} | {
        k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))
    }
    with observation(
        "generate-completion", as_type="generation", input=messages, model=model, model_parameters=params
    ) as generation:
        response = litellm.completion(model=model, messages=messages, temperature=temperature, **kwargs)
        record_generation(generation, response)
    return response.choices[0].message.content or ""


def structured(
    prompt: str,
    schema: type[T] | None = None,
    *,
    model: str | None = None,
    system: str | None = None,
    retries: int = 1,
) -> T | dict:
    """Ask for JSON and validate it against `schema` (or any JSON object when schema is None).

    Uses prompt instructions rather than provider-specific JSON modes so it works with every
    LiteLLM backend. On invalid output the error is fed back and the call retried.
    """
    if schema is not None:
        instructions = (
            "Respond with only a JSON object matching this JSON schema, no prose:\n"
            + json.dumps(schema.model_json_schema())
        )
    else:
        instructions = "Respond with only a JSON object, no prose."
    system = f"{system}\n\n{instructions}" if system else instructions

    schema_name = schema.__name__ if schema is not None else None
    with observation(
        "generate-structured-output",
        as_type="chain",
        input={"schema": schema_name, "max_attempts": retries + 1},
    ) as chain:
        errors: list[str] = []
        last_error: Exception | None = None
        for _ in range(retries + 1):
            raw = _FENCE_RE.sub("", complete(prompt, model=model, system=system).strip())
            try:
                result = _parse(raw, schema)
            except (ValidationError, ValueError) as e:
                errors.append(str(e))
                last_error = e
                prompt = f"{prompt}\n\nYour previous answer was invalid ({e}). Answer again with valid JSON only."
                continue
            chain.update(
                output=result.model_dump() if isinstance(result, BaseModel) else result,
                metadata={"attempts": len(errors) + 1, "validation_errors": errors},
                level="WARNING" if errors else None,
            )
            return result
        chain.update(metadata={"attempts": len(errors), "validation_errors": errors})
        raise last_error


def _parse(raw: str, schema: type[T] | None) -> T | dict:
    if schema is not None:
        return schema.model_validate_json(raw)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return parsed
