# Langflow with modkit installed into Langflow's own Python environment.
# modkit is installed WITHOUT the [mcp] extra so it doesn't disturb Langflow's pinned mcp version.
FROM langflowai/langflow:1.12.4

USER root
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
COPY pyproject.toml README.md /opt/modkit/
COPY src /opt/modkit/src
RUN uv pip install --python "$(command -v python)" --no-cache /opt/modkit
USER user
