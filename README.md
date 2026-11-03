# modkit

A library of reusable back-end modules for client automation projects. You build each module once in
Python and reuse it across clients in three ways:

- **Drag-and-drop blocks** in [Langflow](https://docs.langflow.org/): assemble a client's workflow
  on a canvas and set emails, prompts and models without writing code.
- **MCP tools**: call the same modules from Claude Desktop, Claude Code, Cursor or a Langflow agent.
- **Plain Python**: use them in notebooks, scripts and tests.

Every run is traced in [Langfuse](https://langfuse.com/): inputs, outputs, model, tokens, cost and
errors. Every LLM call goes through LiteLLM, so you can switch models by name.

```text
            ┌──────────────── one Docker stack per client ────────────────┐
            │                                                             │
 team  ───► │  Langflow canvas ──► modkit blocks ─┐                       │
            │                                      ├──► modkit (Python) ──┼──► LiteLLM proxy ──► Claude / GPT / ...
 MCP   ───► │  modkit MCP server ─────────────────┘         │             │
 clients    │                                               ▼             │
            │                                         SMTP / Mailpit      │
            └───────────────────────────────┬─────────────────────────────┘
                                            ▼
                                Langfuse (one project per client)
```

## Modules

| Module | Function | Langflow block | MCP tool |
|---|---|---|---|
| LLM | `complete()`, `structured()` | – (used by the other blocks) | `ask_llm` |
| Data extraction | `extract(source, instructions, fields=..., model=...)` | **Data Extractor** | `extract_data` |
| Email | `send_email(to, subject, body)` | **Email Sender** | `send_email` |

`extract()` accepts a file path (`.pdf`, `.csv`, `.txt`, …), an http(s) URL, or raw text. It returns
a dict that is validated against your field list or a Pydantic schema. If the model returns invalid
JSON, it retries once.

## Repo layout

```text
src/modkit/                 core logic, with no Langflow dependency (the reusable part)
  llm/                      LiteLLM wrapper and JSON/schema output
  extraction/               document loading and extraction
  email/                    SMTP sending
  observability.py          Langfuse tracing helpers (no-op when no keys are set)
  mcp_server.py             exposes the modules as MCP tools
  config.py                 per-client settings (MODKIT_* env vars)
components/modkit_blocks/   thin Langflow wrappers: canvas inputs/outputs → modkit calls
flows/templates/            exported Langflow flows (JSON), reused across clients
deploy/
  docker-compose.yml        Langflow + Postgres + modkit MCP server (+ Mailpit in dev)
  clients/example.env       template for a client's settings (copy per client; real ones are git-ignored)
  scripts/import_flows.py   loads flow templates into a client's Langflow
data/                       client input files, mounted read-only at /data (git-ignored except the sample)
tests/                      pytest, with the LLM, SMTP and Langfuse mocked
```

## Getting started

### Prerequisites
- Python 3.12 and Docker with Compose v2.
- A **LiteLLM proxy key** (or direct provider keys, see `example.env`).
- A **Langfuse** project: [Langfuse Cloud](https://us.cloud.langfuse.com) or self-hosted (see
  [Monitoring](#monitoring-langfuse)). It's optional; tracing turns off when the keys are empty.

### 1. Install and run the tests
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # or: uv sync --extra dev
.venv/bin/pytest
```

### 2. Create a client config
```bash
cp deploy/clients/example.env deploy/clients/client_1.env
```
Fill in:
- `LITELLM_PROXY_API_KEY`
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`
- A strong `LANGFLOW_SUPERUSER_PASSWORD` and `LANGFLOW_SECRET_KEY`. Generate them with
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.

Model names are the proxy's names, for example `vertex_ai.anthropic.claude-sonnet-5-5` or `openai.gpt-5`.
`MODKIT_MODEL_CHOICES` controls the canvas model dropdown.

### 3. Start the stack
```bash
CLIENT=client_1 docker compose -f deploy/docker-compose.yml --profile dev up -d --build
```

| Service | URL |
|---|---|
| Langflow (login: `LANGFLOW_SUPERUSER` / `LANGFLOW_SUPERUSER_PASSWORD`) | http://localhost:7860 |
| modkit MCP server | http://localhost:8000/mcp |
| Mailpit test inbox (`dev` profile; catches all email) | http://localhost:8025 |

All ports are bound to `127.0.0.1`. Put a reverse proxy with authentication in front of them before
exposing anything.

### 4. Build or import flows
- **Build:** in Langflow, open **Modkit Blocks** in the sidebar. See
  [flows/templates/README.md](flows/templates/README.md) for a step-by-step extract → email flow.
  Export finished flows into `flows/templates/`.
- **Import** existing templates into a client instance. Create the API key under Langflow
  **Settings → Langflow API Keys**:
  ```bash
  python deploy/scripts/import_flows.py --url http://localhost:7860 --api-key <key> flows/templates/*.json
  ```

### Day-to-day commands
```bash
C="docker compose -f deploy/docker-compose.yml"
CLIENT=client_1 $C --profile dev up -d --build   # after changing src/modkit (it's baked into the images)
CLIENT=client_1 $C restart langflow              # after changing components/ (mounted live)
CLIENT=client_1 $C logs -f langflow
CLIENT=client_1 $C --profile dev down            # stop; data volumes are kept
```

## Using the modules from Python

Load a client's settings first. LiteLLM reads its proxy settings from the environment:

```bash
set -a; source deploy/clients/client_1.env; set +a
```

```python
from modkit import extract, send_email

data = extract("data/sample_invoice.txt", "Extract the invoice details",
               fields=["vendor", "invoice_number", "total", "due_date"],
               model="vertex_ai.anthropic.claude-haiku-5-5")
send_email("me@example.com", "Invoice summary", str(data))
```

## MCP

```bash
.venv/bin/modkit-mcp                                         # stdio
MCP_TRANSPORT=streamable-http .venv/bin/modkit-mcp           # http://127.0.0.1:8000/mcp
claude mcp add modkit -- /path/to/.venv/bin/modkit-mcp       # register with Claude Code
npx @modelcontextprotocol/inspector .venv/bin/modkit-mcp     # inspect and call tools
```

- **Inside Langflow:** add an **MCP Tools** component pointing at `http://modkit-mcp:8000/mcp` to give
  agents these tools.
- **To publish a whole flow as an MCP tool:** open the flow and choose **Share → MCP Server**.

## Monitoring (Langfuse)

Use [Langfuse Cloud](https://us.cloud.langfuse.com), or self-host it once as its own stack:
`git clone https://github.com/langfuse/langfuse && cd langfuse && docker compose up -d`. That serves
<http://localhost:3000>, which containers reach as `http://host.docker.internal:3000`.

Create one Langfuse project per client and put its keys in that client's env file. Langflow traces
each flow run, and the modkit blocks nest their observations inside that trace, so one flow run is one
trace:

```text
extract-data          span        input: source, instructions, fields, model; output: the extracted dict
├─ load-document      retriever   file or URL only (skipped for raw text); WARNING when no text is extracted
└─ generate-structured-output  chain   attempts and validation errors; WARNING when a retry was needed
   └─ generate-completion      generation  messages in, assistant reply out, model, params, tokens, cost
send-email            tool        recipients, subject, body; ERROR on failure
```

- **Names are an API.** Dashboards and evaluators filter on observation names, so don't rename them
  casually.
- **MCP calls** are tagged `mcp`.
- **Cost and model:** cost comes from the LiteLLM proxy, which prices its own model aliases. The
  provider model the alias resolved to is stored in metadata as `resolved_model`.
- **Environments:** set `LANGFUSE_TRACING_ENVIRONMENT` (`production`, `staging`, `development`) to keep
  test runs out of production views.
- **Turning it off:** `LANGFUSE_TRACING_ENABLED=false` disables tracing without removing the keys.

## Adding a module

1. **Core:** write the function in `src/modkit/<module>/` and add tests. Wrap its body in
   `with observation("verb-noun", as_type=..., input={...}) as obs:` from `modkit.observability`, and
   call `obs.update(output=...)` before returning.
   - Pick the most specific type: `generation`, `tool`, `retriever`, `chain` or `span`.
   - Set `input` to the meaningful arguments only, never settings or credentials.
   - Add the new name to `tests/test_tracing.py`.
2. **Langflow block:** add a wrapper in `components/modkit_blocks/` and register it in that folder's
   `__init__.py`. Make the module call inside `with child_of(*langflow_span(self)):` so it joins the
   flow's trace.
3. **MCP tool:** add an `@mcp.tool()` in `src/modkit/mcp_server.py` that makes the call inside
   `with trace_attributes(tags=["mcp"]):`.

Keep business logic in step 1. Steps 2 and 3 should stay thin wrappers, so the platform can be swapped
without touching the logic.

## Security notes

- **Never commit** `deploy/clients/<client>.env` or anything in `data/`. Both are git-ignored.
- **Exported flows** can include values typed into components, such as email addresses, prompts, and
  sometimes API keys. Check the JSON before committing it to `flows/templates/`.
- **The MCP server's `extract_data`** reads local files and URLs. Only expose the HTTP transport on a
  trusted network.
- **Langflow:** keep `LANGFLOW_AUTO_LOGIN=false` and `LANGFLOW_MCP_SERVERS_LOCKED=true` in client
  deployments.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `permission denied ... docker.sock` | Add yourself to the `docker` group (`sudo usermod -aG docker $USER`), then open a new session, or prefix commands with `sg docker -c "..."`. |
| LiteLLM warns about failing to fetch the model cost map (`CERTIFICATE_VERIFY_FAILED`) | Corporate TLS inspection is blocking GitHub. Set `LITELLM_LOCAL_MODEL_COST_MAP=True`, which is already in `example.env`. |
| Modkit blocks missing from the Langflow sidebar | Check `LANGFLOW_COMPONENTS_PATH` and that `components/modkit_blocks/__init__.py` exports the block, then restart Langflow. |
| Code changes not showing in Docker | `src/modkit` is baked into the images, so re-run `up -d --build`. |
| No traces in Langfuse | Keys empty or wrong project, or `LANGFUSE_BASE_URL` unreachable from the container. |

## Stack

| Component | Licence |
|---|---|
| [Langflow](https://github.com/langflow-ai/langflow) | MIT |
| [LiteLLM](https://github.com/BerriAI/litellm) | MIT |
| [Langfuse](https://github.com/langfuse/langfuse) | MIT core |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT |
| Pydantic, pypdf, httpx | MIT / BSD |
