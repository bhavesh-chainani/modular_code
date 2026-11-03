"""Data extraction module: source + instructions (+ optional fields/schema) -> JSON dict."""

from pathlib import Path

from pydantic import BaseModel, create_model

from modkit.extraction.loaders import load_text
from modkit.llm import structured
from modkit.observability import observation


def schema_from_fields(fields: list[str]) -> type[BaseModel]:
    """Build a schema of optional string fields, e.g. from a comma-separated list typed on the canvas."""
    return create_model("Extraction", **{name: (str | None, None) for name in fields})


def extract(
    source: str | Path,
    instructions: str,
    *,
    fields: list[str] | None = None,
    schema: type[BaseModel] | None = None,
    model: str | None = None,
) -> dict:
    """Extract data from `source`. Pass `schema` for full typing, `fields` for quick string fields,
    or neither for free-form JSON."""
    with observation(
        "extract-data",
        input={
            "source": str(source),
            "instructions": instructions,
            "fields": fields,
            "schema": schema.__name__ if schema is not None else None,
            "model": model,
        },
    ) as obs:
        if schema is None and fields:
            schema = schema_from_fields(fields)
        prompt = f"{instructions}\n\n<document>\n{load_text(source)}\n</document>"
        result = structured(prompt, schema, model=model)
        data = result.model_dump() if isinstance(result, BaseModel) else result
        obs.update(output=data)
    return data
