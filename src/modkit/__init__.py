"""modkit: reusable client modules. Core logic only; Langflow and MCP are thin wrappers on top."""

from modkit.email import send_email
from modkit.extraction import extract
from modkit.llm import complete, structured

__all__ = ["complete", "structured", "extract", "send_email"]
