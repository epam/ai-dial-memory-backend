<h1 align="center">
         AI DIAL MEMORY
    </h1>
    <p align="center">
        <p align="center">
        <a href="https://dialx.ai/">
          <img src="https://dialx.ai/logo/dialx_logo.svg" alt="About DIALX">
        </a>
    </p>
<h4 align="center">
    <a href="https://discord.gg/ukzj9U9tEe">
        <img src="https://img.shields.io/static/v1?label=DIALX%20Community%20on&message=Discord&color=blue&logo=Discord&style=flat-square" alt="Discord">
    </a>
</h4>

AI DIAL Memory is a persistent memory service for AI agents running on the [DIAL platform](https://dialx.ai/). It gives
agents long-term memory across conversations by exposing four MCP tools for storing and retrieving facts. All data is
stored in the user's own DIAL file storage bucket — the server itself is fully stateless and horizontally scalable.

## Quick highlights

- Two memory tiers: **core** (permanent user facts, always injected) and **episodic** (session events, searchable by
  context).
- MCP server (`/mcp`) plus a REST management API on the same process — no separate sidecar needed.
- Fully stateless: memory lives in DIAL file storage (BLOB); any instance handles any request.
- Per-user isolation by design — each `Api-Key` maps to its own isolated storage bucket.
- Schema-driven DIAL Application Type: live JSON schema served at `/v1/configuration-support/application-schema`.

## How It Works

Each request carries an `Api-Key` header (forwarded by DIAL Core). The service resolves the caller's DIAL file storage
home from that key and syncs a LanceDB table packed as `memory/memory.tar.gz` to a local scratch directory, performs the
operation, then syncs the updated archive back to DIAL storage. A per-bucket `asyncio.Lock` prevents concurrent writes.

```
HTTP request (from DIAL Core)
  │
  ├── /mcp  →  FastMCP (streamable HTTP)
  │              └── Tools: store_memory, search_archive, prime_memories, get_skill
  │                     └── MemoryService
  │                            ├── StorageSync  (sync-down / sync-up via DIAL file storage)
  │                            └── LanceDbMemoryRepository  (local LanceDB ops)
  │
  └── /memory*, /v1/configuration-support/*  →  FastAPI REST
```

## MCP Tools

The MCP server is mounted at `/mcp` and named `ai-dial-memory`. All tools require an `Api-Key` header.

| Tool | Description |
|---|---|
| `store_memory` | Append a new memory row (`core` or `episodic`) with a content string, context label, and importance score (0.0–1.0). |
| `search_archive` | Full-text search over **episodic** memories. Returns matching `MemoryRow` objects. |
| `prime_memories` | Called once at dialogue start. Returns top-N core memories (by importance) plus episodic memories scoped to the current `app_name`. |
| `get_skill` | Returns the embedded skill instructions markdown. Agents call this once to load guidance on when/how to use memory tools. |

### Memory types

| Type | Scope | Retrieval |
|---|---|---|
| `core` | Universal user facts (name, preferences) | Always injected via `prime_memories` ranked by importance |
| `episodic` | Session events scoped to a deployment | Injected via `prime_memories` filtered by `app_name`; searchable via `search_archive` |

### Importance scores

| Range | Behaviour |
|---|---|
| 0.9–1.0 | Always injected at dialogue start |
| 0.7–0.9 | Injected when context-relevant |
| < 0.7 | Low priority; surface only via search |

## REST API

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/memory` | `Api-Key` | List all memory rows. Optional `?memory_type=core\|episodic`. |
| `GET` | `/memory/{id}` | `Api-Key` | Get a single row by UUID. Returns 404 if not found. |
| `DELETE` | `/memory/{id}` | `Api-Key` | Hard-delete a row. Returns 204. |
| `GET` | `/v1/configuration-support/application-schema` | — | Live JSON schema for DIAL Core registration. |

## Configuration

### Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `DIAL_URL` | — | Yes | Base URL of the AI DIAL Core API |
| `LOG_LEVEL` | `INFO` | No | Root logger level (`DEBUG` / `INFO` / `WARNING` / `ERROR`) |
| `TMP_DIR` | `/tmp` | No | Local scratch directory for LanceDB sync cache |
| `HOST` | `0.0.0.0` | No | Uvicorn bind host |
| `PORT` | `8000` | No | Uvicorn bind port |

### Per-App Configuration

DIAL Core injects per-instance settings via the `X-Dial-Application-Properties` header on every request.

| Property | Default | Description |
|---|---|---|
| `tier1_limit` | `5` | How many top core memories to inject at dialogue start |
| `tier2_limit` | `10` | How many episodic memories to inject per `app_name` scope |

### Hooks integration

AI DIAL Memory is designed to work with [Quick Apps Hooks](https://github.com/epam/ai-dial-quickapps). Add a
`prime_memories` hook to your Quick App manifest to automatically inject memories at the start of every dialogue:

```json
{
  "hooks": [
    {
      "kind": "tool_call",
      "event": "on_request_start",
      "toolset_name": "memory_server",
      "tool_name": "prime_memories",
      "arguments": { "app_name": "my-app" },
      "frequency": "always"
    }
  ]
}
```

## Local Development

### Pre-requisites

1. Install Python 3.13
    - macOS (Homebrew): `brew install python@3.13`
    - Official downloads: https://www.python.org/downloads/

2. Install [Poetry](https://python-poetry.org/docs/#installation) (recommended: pipx or the official installer).

3. Install Make
    - macOS: usually preinstalled.
    - Windows: https://gnuwin32.sourceforge.net/packages/make.htm or Chocolatey.
    - Ensure `make` is in PATH (`which make`).

> **Note:** LanceDB has no Windows wheel. On Windows the package is stubbed out for test runs; storage-touching code
> must be exercised on Linux/macOS or inside a container.

### Setup

1. Clone the repository and create a virtual environment:

    ```bash
    make init_venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    ```

2. Install dev dependencies:

    ```bash
    make install_dev
    ```

3. Create a `.env` file:

    ```bash
    cp .env.template .env
    # Set DIAL_URL to your DIAL Core endpoint, e.g. http://localhost:8090
    ```

### Run

Start the service (connects to the DIAL Core instance defined in `.env`):

```bash
python src/main.py
```

The service starts on `http://0.0.0.0:8000`. The MCP endpoint is at `http://localhost:8000/mcp`.

### Utils

```bash
make format         # Format all source files
make lint           # Run all linters (ruff + mypy)
make test           # Run all unit tests
make test ARGS="-k test_name -x"  # Run specific tests / fail fast
make test_cov       # Run tests with coverage report
```

### Generate the DIAL application schema

```bash
python src/scripts/dump_app_schema.py          # Write docs/generated-app-schema.json
python src/scripts/dump_app_schema.py --check  # Verify schema is up to date (CI)
```

## Deployment

### Registering with DIAL Core

After deploying the service, register the application type so DIAL Core can validate and surface it:

1. Generate the schema:
    ```bash
    python src/scripts/dump_app_schema.py
    ```
2. Mount `docs/generated-app-schema.json` in DIAL Core's configuration (e.g. via Helm ConfigMap or
   `PREDEFINED_EXTRA_PATHS`).
3. Point `DIAL_URL` at your DIAL Core API endpoint.
4. Create a DIAL application record whose endpoint points at this service.

Alternatively, DIAL Core can fetch the live schema directly from
`GET /v1/configuration-support/application-schema` — no static file required.

## More

For more information about DIAL and its components, visit the [DIAL documentation](https://dialx.ai/docs). Join the DIAL
community on [Discord](https://discord.gg/ukzj9U9tEe) for support and collaboration.
