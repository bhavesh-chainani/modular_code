# Stand-alone modkit MCP server (streamable HTTP), used by Langflow's MCP Tools component
# and by MCP clients such as Claude Desktop / Claude Code.
FROM python:3.12-slim

WORKDIR /opt/modkit
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[mcp]"

ENV MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000
EXPOSE 8000
CMD ["modkit-mcp"]
