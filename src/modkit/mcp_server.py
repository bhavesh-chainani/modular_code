"""Expose modkit modules as MCP tools.

    modkit-mcp                                   # stdio (Claude Desktop / Claude Code / Cursor)
    MCP_TRANSPORT=streamable-http modkit-mcp     # HTTP on MCP_HOST:MCP_PORT (Langflow MCP Tools component)

Note: extract_data reads local files and URLs; only run the HTTP transport on a trusted network.
"""

import os

from mcp.server.mcpserver import MCPServer

from modkit import complete, extract, send_email
from modkit.observability import trace_attributes

mcp = MCPServer(
    "modkit",
    instructions="Reusable client modules: LLM calls, document data extraction, and email sending.",
)


@mcp.tool()
def extract_data(
    source: str,
    instructions: str,
    fields: list[str] | None = None,
    model: str | None = None,
) -> dict:
    """Extract structured data from a URL, a file path, or raw text.

    Args:
        source: http(s) URL, file path (.pdf, .csv, .txt, ...) or the raw text itself.
        instructions: What to extract, e.g. "Extract the invoice details".
        fields: Optional field names to return; omit for free-form JSON.
        model: Optional LiteLLM model string; defaults to the deployment's default model.
    """
    with trace_attributes(tags=["mcp"]):
        return extract(source, instructions, fields=fields, model=model)


@mcp.tool(name="send_email")
def send_email_tool(to: str, subject: str, body: str, html: bool = False) -> dict:
    """Send an email. `to` may be a comma-separated list of addresses."""
    with trace_attributes(tags=["mcp"]):
        return send_email(to, subject, body, html=html)


@mcp.tool()
def ask_llm(prompt: str, model: str | None = None, system: str | None = None) -> str:
    """Run a single prompt through any LiteLLM-supported model."""
    with trace_attributes(tags=["mcp"]):
        return complete(prompt, model=model, system=system)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport,
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8000")),
        )


if __name__ == "__main__":
    main()
