# Project State — ai-dial-memory-mcp

---

## Current Goal

Build the **Memory MCP Server** — a standalone Python service that gives DIAL Quick Apps (2.0) persistent, per-user memory. The server is the single source of truth for all memory data: it stores facts and interaction history, manages the underlying storage, computes search relevance, and exposes its capabilities both as **MCP tools** (for AI agents) and as a **REST API** (for UI clients).

**Out of scope for this server:** memory skill injection, system prompt assembly, and per-interaction episodic persistence. Those are quickapps-backend responsibilities. This server only handles storage and retrieval.

---

## Context

### Background

Quick Apps (2.0) is a composer for DIAL applications that wires tools, REST APIs, and MCP servers with an LLM orchestrator. Today, agents have no memory across conversations — every session starts blank. Users need the AI to remember who they are, what they prefer, and what happened in past sessions.

### What we are building

A **DIAL Application Type** deployed as an MCP endpoint + REST API. A single server instance serves all users; user isolation is achieved via storage paths, not separate instances.

### Memory data model

All memory lives in a single **LanceDB table** (`memory.lance/`) stored in the user's personal bucket in DIAL file storage. Two logical types share the same table (distinguished by a `memory_type` column):

| Type | Purpose | Who writes |
|------|---------|------------|
| `core` | Permanent user facts and preferences (name, language, project details) | Agent via `store_memory` |
| `episodic` | Record of past interactions and significant decisions | quickapps-backend (post-turn hook, outside this server's scope for now — but the table must support it) |

**Append-only invariant**: facts are never overwritten. If two conflicting facts exist, both are stored and the retrieval layer surfaces the contextually appropriate one.

### Storage strategy

DIAL file storage is a cloud-agnostic BLOB (S3, GCS, Azure Blob, or local filesystem). LanceDB needs a local filesystem. The server uses a **sync-down / sync-up** pattern:
1. Before any read or write: pull `memory.lance/` from DIAL file storage to local `/tmp`.
2. Perform the LanceDB operation locally.
3. After any write: push the updated `memory.lance/` back to DIAL file storage.

This keeps the server fully stateless and horizontally scalable.

### Two-phase search strategy

| Phase | Core-fact retrieval | `search_archive` | Embedding |
|-------|---------------------|-----------------|-----------|
| **Phase 1** (initial) | Full-text search (keyword match) | FTS over episodic rows | No vectors — `vector` column is null |
| **Phase 2** (future) | Cosine similarity + importance weighting | ANN via LanceDB | Per-row float vector; `embedding_model` column guards against cross-model comparisons |

**Phase 1 must be delivered first.** Phase 2 is a follow-up that requires an embedding API integration (e.g. DIAL embeddings endpoint).

### Memory scope

First iteration: **one memory per user**, stored at:
```
files/{bucket}/memory/memory.lance/
```
where `{bucket}` is resolved from the caller's DIAL identity via `GET /v1/bucket`.

Future iteration (out of scope now): app-scoped memory at `files/{bucket}/apps/{quickapp_id}/memory/memory.lance/`. The server must be **path-agnostic by design** so this extension requires zero server changes — the caller passes the path.

---

## Functional Requirements

### FR-1: Agent-facing MCP tools

The server MUST expose two MCP tools:

| Tool | Description | Parameters |
|------|-------------|------------|
| `store_memory` | Append a new memory row. Append-only — never overwrites. | `content: str`, `memory_type: Literal["core","episodic"]`, `context: str`, `importance: float (0.0–1.0)` |
| `search_archive` | Search episodic history. Used when agent needs to recall past events not in the current context window. | `query: str` |

**Authentication on MCP calls**: When the LLM agent decides to call a tool, quickapps-backend is the one that executes the MCP tool invocation against the Memory MCP server. quickapps-backend forwards the user's per-request API key as a header on that call. The server reads this key and uses it to resolve the user's bucket via `GET /v1/bucket` — the same mechanism used for REST API calls. User isolation is therefore enforced uniformly across both MCP tool calls and REST routes.

### FR-2: REST API for UI clients

The server MUST expose HTTP routes for read/delete operations (agents are the only writers):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/memory` | List all memory rows for the authenticated user. Supports `memory_type` filter. |
| `GET` | `/memory/{id}` | Get a single memory row by ID. |
| `DELETE` | `/memory/{id}` | Hard-delete a memory row. |

Routes are proxied through DIAL Core; the caller's identity is forwarded and the server derives the correct storage path from it. Cross-user access is structurally impossible.

### FR-3: Per-user LanceDB storage in DIAL file storage

- Each user's memory is stored as `files/{bucket}/memory/memory.lance/` in DIAL file storage.
- The server resolves `{bucket}` via `GET /v1/bucket` using the caller's forwarded identity.
- The server must sync LanceDB data down before reading and sync back up after writing.

### FR-4: LanceDB table schema

| Column | Type | Notes |
|--------|------|-------|
| `id` | `string` | UUID, set at write time |
| `memory_type` | `string` | `"core"` or `"episodic"` |
| `content` | `string` | Full text of the memory |
| `context` | `string` | Scope hint (e.g. `"project-alpha"`, `"user-prefs"`) |
| `importance` | `float32` | 0.0–1.0; drives retrieval ranking |
| `embedding_model` | `string` | Model that produced the vector; null in Phase 1 |
| `vector` | `list<float32>[N]` | Embedding; null in Phase 1 |
| `timestamp` | `timestamp[us]` | Creation time |
| `access_count` | `int32` | Incremented on retrieval; reserved for future decay logic |

### FR-5: Core-fact retrieval endpoint (for quickapps injection)

quickapps-backend calls this endpoint **once per agent turn, before the agent runs**, to retrieve the core facts that will be injected into the system prompt for that turn. The agent never calls this endpoint — it is a server-to-server call only.

#### HTTP contract

```
GET /memory/retrieve?query=<user message>&tier1_limit=5&tier2_limit=10
Api-Key: <per-request API key forwarded by DIAL Core>
```

- `query` — the user's current message text. Used by the server for Tier 2 FTS (Phase 1) or vector search (Phase 2). Required.
- `tier1_limit` — optional, default 5. Number of top facts returned by importance.
- `tier2_limit` — optional, default 10. Number of facts matched to `query`.
- The API key is a per-request key forwarded by DIAL Core. The server uses it to resolve the user's bucket and authenticate downstream DIAL API calls.

#### Response

```json
{
  "facts": [
    {
      "id": "uuid-1",
      "content": "User prefers TypeScript for all code examples",
      "context": "user-prefs",
      "importance": 0.9,
      "timestamp": "2026-03-28T10:00:00Z"
    },
    {
      "id": "uuid-2",
      "content": "Project Alpha uses CockroachDB",
      "context": "project-alpha",
      "importance": 0.85,
      "timestamp": "2026-03-30T09:00:00Z"
    }
  ]
}
```

The list is already **merged and deduplicated by `id`**. Tier 1 facts always appear first. quickapps-backend formats these into a system prompt block (e.g. "Known facts about you: …") and injects it — no further processing is needed on the server.

#### Two-tier retrieval logic

| Tier | Query | Scoring | Default limit |
|------|-------|---------|---------------|
| **Tier 1** — always inject | No query. `SELECT … WHERE memory_type='core' ORDER BY importance DESC` | Importance only | 5 |
| **Tier 2** — context inject | FTS (Phase 1) or vector search (Phase 2) over `memory_type='core'`, matched to `query` | `final_score = similarity * (0.5 + importance * 0.5)` | 10 |

Results from both tiers are merged and deduplicated by `id` before returning. Tier 1 facts always appear before Tier 2 facts in the response list.

#### Pre-turn injection flow

```
quickapps-backend                    Memory MCP Server               LanceDB (local /tmp)
       |                                     |                               |
       |  GET /memory/retrieve               |                               |
       |  ?query=<user message>      ------> |                               |
       |                                     |  sync down memory.lance/  --> |
       |                                     |  Tier 1: top-5 by importance  |
       |                                     |  Tier 2: FTS match to query   |
       |                                     |  merge + deduplicate          |
       |  { facts: [...] }           <------ |                               |
       |                                     |                               |
       | inject facts into system prompt     |                               |
       | run agent turn                      |                               |
```

No sync-up after this call — it is a read-only operation. `access_count` is incremented for returned rows (write is batched or fire-and-forget to avoid blocking the agent turn).

### FR-6: DIAL Application Type integration

- The server registers in DIAL Core as an Application Type with an MCP endpoint and custom REST routes.
- It reads its configuration via the DIAL SDK's application properties mechanism (`request_dial_application_properties()`).
- No custom config file — all admin settings are managed via DIAL Core.

---

## Non-functional Requirements

- **Stateless**: any server instance can handle any request; no in-process state between requests.
- **Single-user isolation**: enforced structurally via DIAL file storage paths, not application-level access control.
- **Language**: Python (consistent with the DIAL ecosystem and existing `pyproject.toml`).
- **MCP transport**: HTTP (DIAL Core routes MCP calls over HTTP).
- **Phase 1 search**: FTS / keyword match only; no embedding model dependency in Phase 1.
- **Observability**: structured logging; errors in sync must not silently corrupt storage.

---

## Agent Tool Call Flows

These examples show how an agent uses the two MCP tools during a conversation. The agent calls these tools autonomously based on the Memory Skill instructions. The Memory MCP server only executes what it receives — it has no opinion on when or why a tool is called.

> In all flows below, **core facts are already injected into the system prompt** by quickapps-backend *before* the agent turn starts (via FR-5). The agent does not need to call a tool to read core memory — it's just there. The tools are only called when the agent wants to **write** new information or **search episodic history**.

---

### Flow 1: User states a preference → agent stores a core fact

The agent recognises a permanent preference and saves it without being asked.

```
User:  "Always give me code examples in TypeScript."

[Agent decides to store a core fact]
→ store_memory(
    content="User prefers TypeScript for all code examples",
    memory_type="core",
    context="user-prefs",
    importance=0.9
  )
← { id: "uuid-1", stored: true }

Agent: "Got it — I'll use TypeScript for all code examples from now on."
```

Next session — quickapps-backend injects the stored fact into the system prompt before the agent runs. No tool call needed; the fact is already in context.

---

### Flow 2: User explicitly asks to remember something → agent stores a core fact

```
User:  "Remember that project Alpha uses a PostgreSQL database, not MySQL."

→ store_memory(
    content="Project Alpha uses PostgreSQL, not MySQL",
    memory_type="core",
    context="project-alpha",
    importance=0.8
  )
← { id: "uuid-2", stored: true }

Agent: "Noted — I'll remember that Project Alpha runs on PostgreSQL."
```

---

### Flow 3: User references a past event → agent searches episodic history

The current context window does not contain the referenced conversation. The agent uses `search_archive` to retrieve it.

```
User:  "Last week we debugged a memory leak in the data pipeline — can you remind me what the fix was?"

[Agent detects a reference to a past event outside the current context]
→ search_archive(query="memory leak fix data pipeline")
← [
    {
      id: "uuid-8",
      memory_type: "episodic",
      content: "Debugged memory leak in the ETL pipeline. Root cause: unbounded cache in DataLoader. Fix: added LRU cache with max_size=500.",
      timestamp: "2026-03-24T14:32:00Z"
    }
  ]

Agent: "In that session we traced the leak to an unbounded cache in DataLoader.
        The fix was switching to an LRU cache with max_size=500."
```

---

### Flow 4: Significant decision reached mid-conversation → agent stores an episodic memory

The agent autonomously records a decision that is worth remembering for future sessions.

```
User:  "OK, let's go with a microservices architecture for the new backend."

[Agent decides this is a significant decision worth persisting]
→ store_memory(
    content="Team decided to use microservices architecture for the new backend (over monolith). Decision made 2026-03-30.",
    memory_type="episodic",
    context="project-beta",
    importance=0.75
  )
← { id: "uuid-15", stored: true }

Agent: "Microservices it is. I'll keep that in mind for future sessions on this project."
```

---

### Flow 5: Conflicting facts — agent stores without overwriting, surfaces both

The user corrects a previously stored fact. Both rows coexist; the agent uses context to pick the right one.

```
[Previously stored — uuid-2]
content="Project Alpha uses PostgreSQL, not MySQL"

User:  "Actually, we migrated Project Alpha to CockroachDB last month."

→ store_memory(
    content="Project Alpha migrated from PostgreSQL to CockroachDB in February 2026",
    memory_type="core",
    context="project-alpha",
    importance=0.85
  )
← { id: "uuid-22", stored: true }

Agent: "Updated — I'll use CockroachDB for Project Alpha going forward."
```

Both `uuid-2` (PostgreSQL) and `uuid-22` (CockroachDB) exist in storage. On the next session, Tier 2 retrieval matches the current query to `uuid-22` (higher importance, more recent) and injects it. If both appear, the agent asks the user to confirm which is current — which is the correct behaviour.

---

### Flow 6: Combined flow — search then store

The agent finds past context and records a new decision that builds on it.

```
User:  "We talked about caching strategies before — based on that, let's go with Redis."

→ search_archive(query="caching strategy discussion")
← [
    {
      id: "uuid-31",
      content: "Discussed caching options: Redis, Memcached, in-process LRU. Redis favoured for its persistence and pub/sub.",
      timestamp: "2026-03-15T10:00:00Z"
    }
  ]

[Agent uses the retrieved context to answer, then stores the decision]
→ store_memory(
    content="Decided to use Redis for caching. Chosen over Memcached and in-process LRU for persistence and pub/sub support.",
    memory_type="core",
    context="project-beta",
    importance=0.8
  )
← { id: "uuid-32", stored: true }

Agent: "Based on our earlier discussion where Redis came out ahead for persistence
        and pub/sub, that's a solid call. I've saved the decision."
```

---

## Architecture

### Overview

The server is a **FastAPI** application exposing two interfaces — MCP tools (HTTP transport) and a REST API — backed by a LanceDB-on-BLOB storage tier and a DIAL SDK integration layer. All dependencies are wired via **[Injector](https://injector.readthedocs.io/)** (Google Guice-style DI for Python).

---

### Module / Directory Layout

```
ai-dial-memory-mcp/
├── main.py                        # Entry point — creates Injector, builds FastAPI app, starts Uvicorn
├── pyproject.toml
└── app/
    ├── di/
    │   └── modules.py             # Injector Module definitions (AppModule, StorageModule, DialModule)
    ├── config/
    │   └── settings.py            # Pydantic BaseSettings — env vars + DIAL app properties
    ├── models/
    │   └── memory.py              # Pydantic domain models: MemoryRow, StoreMemoryInput, RetrieveResponse, …
    ├── api/
    │   ├── router.py              # Mounts sub-routers; wires Injector into FastAPI dependency injection
    │   ├── memory_router.py       # GET /memory, GET /memory/{id}, DELETE /memory/{id}  (FR-2)
    │   └── retrieve_router.py     # GET /memory/retrieve  (FR-5, server-to-server)
    ├── mcp/
    │   └── tools.py               # MCP tool definitions: store_memory, search_archive  (FR-1)
    ├── services/
    │   └── memory_service.py      # MemoryService — all business logic; orchestrates repo + sync
    ├── storage/
    │   ├── sync.py                # StorageSync — sync-down / sync-up with DIAL file storage
    │   └── repository.py          # MemoryRepository — LanceDB table operations (append, query, delete)
    ├── dial/
    │   └── client.py              # DialClient — thin wrapper around aidial-client (bucket resolution, file upload/download)
    └── middleware/
        └── auth.py                # FastAPI dependency: extract Api-Key header → resolve user bucket
```

---

### Component Breakdown

| Component | Exists? | Role |
|-----------|---------|------|
| `main.py` | Yes (stub) | Wire Injector → build FastAPI app → start server |
| `app/config/settings.py` | No — create | Pydantic `BaseSettings`; reads env vars; exposes DIAL app properties |
| `app/models/memory.py` | No — create | All shared Pydantic models (domain + API contracts) |
| `app/di/modules.py` | No — create | Injector `Module` subclasses binding interfaces to implementations |
| `app/middleware/auth.py` | No — create | FastAPI dependency that extracts the `Api-Key` header and resolves the user's bucket |
| `app/dial/client.py` | No — create | `DialClient` wrapping `aidial-client`; bucket resolution, file upload/download |
| `app/storage/sync.py` | No — create | `StorageSync` — sync-down before ops, sync-up after writes |
| `app/storage/repository.py` | No — create | `MemoryRepository` — LanceDB append, FTS query, delete, schema creation |
| `app/services/memory_service.py` | No — create | `MemoryService` — orchestrates sync + repo; implements store, search, retrieve |
| `app/mcp/tools.py` | No — create | MCP tool handlers; thin wrappers over `MemoryService` |
| `app/api/memory_router.py` | No — create | FastAPI REST routes for FR-2 |
| `app/api/retrieve_router.py` | No — create | FastAPI REST route for FR-5 |
| `app/api/router.py` | No — create | Mounts all sub-routers; bridges Injector → FastAPI |

---

### Key Interfaces and Data Contracts

```python
# app/models/memory.py

class MemoryRow(BaseModel):
    id: str                              # UUID
    memory_type: Literal["core", "episodic"]
    content: str
    context: str
    importance: float                    # 0.0–1.0
    embedding_model: str | None          # null in Phase 1
    vector: list[float] | None           # null in Phase 1
    timestamp: datetime
    access_count: int

class StoreMemoryInput(BaseModel):
    content: str
    memory_type: Literal["core", "episodic"]
    context: str
    importance: float = Field(ge=0.0, le=1.0)

class StoreMemoryOutput(BaseModel):
    id: str
    stored: bool

class RetrieveRequest(BaseModel):
    query: str
    tier1_limit: int = 5
    tier2_limit: int = 10

class RetrieveResponse(BaseModel):
    facts: list[MemoryRow]
```

```python
# app/storage/repository.py  (interface sketch)

class MemoryRepository(ABC):
    def append(self, bucket: str, row: MemoryRow) -> None: ...
    def get(self, bucket: str, id: str) -> MemoryRow | None: ...
    def list(self, bucket: str, memory_type: str | None) -> list[MemoryRow]: ...
    def delete(self, bucket: str, id: str) -> None: ...
    def fts_search(self, bucket: str, query: str, memory_type: str, limit: int) -> list[MemoryRow]: ...
    def top_by_importance(self, bucket: str, memory_type: str, limit: int) -> list[MemoryRow]: ...
```

```python
# app/dial/client.py  (interface sketch)

class DialClient(ABC):
    async def resolve_bucket(self, api_key: str) -> str: ...
    async def download(self, api_key: str, remote_path: str, local_path: Path) -> None: ...
    async def upload(self, api_key: str, local_path: Path, remote_path: str) -> None: ...
```

---

### Design Patterns and Rationale

| Pattern | Where | Rationale |
|---------|-------|-----------|
| **Repository** | `MemoryRepository` | Decouples LanceDB from the service layer; Phase 2 vector search is a new implementation, not a code change |
| **Sync Gateway** (custom) | `StorageSync` | Encapsulates the sync-down/sync-up lifecycle; every consumer gets atomic "fetch → operate → flush" semantics without knowing about BLOB details |
| **Service Layer** | `MemoryService` | Single place for business logic (two-tier retrieval, deduplication, locking); API and MCP handlers are thin call-throughs |
| **Dependency Injection (Injector)** | `app/di/modules.py` | All wiring is explicit and testable; no global singletons; `AppModule` composes `StorageModule` + `DialModule` |
| **Strategy (Phase 2)** | `SearchStrategy` interface | FTS (Phase 1) and vector search (Phase 2) are swappable without touching `MemoryService` |

---

### Dependency Injection Design (Injector)

Three `Module` subclasses compose into one root `AppModule`:

```python
class DialModule(Module):
    # Binds DialClient → AiDialClientImpl
    # Provides Settings (singleton)

class StorageModule(Module):
    # Binds MemoryRepository → LanceDbMemoryRepository
    # Binds StorageSync → DialStorageSync
    # Binds SearchStrategy → FtsSearchStrategy  (Phase 1)

class AppModule(Module):
    # Composes DialModule + StorageModule
    # Provides MemoryService
```

`main.py` creates `Injector([AppModule()])`. FastAPI route handlers receive their `MemoryService` via a `Depends(...)` factory that calls `injector.get(MemoryService)` — keeping FastAPI's own DI for HTTP concerns (header extraction, request validation) and Injector for the object graph.

---

### Cross-cutting Concerns

**Authentication / User Identity**
- Every request (MCP and REST) must carry an `Api-Key` header.
- A FastAPI dependency (`app/middleware/auth.py`) extracts the key and calls `DialClient.resolve_bucket()` to produce a `UserContext(api_key, bucket)`.
- `UserContext` is passed down through the service and repository — it is never stored as process state.

**Concurrency / Locking**
- Concurrent requests from the same user are serialized by a per-bucket `asyncio.Lock` held in `StorageSync`.
- Lock granularity is the bucket ID, so different users are never blocked by each other.

**Error Handling**
- `StorageSync` failures (upload/download errors) are raised as `StorageSyncError`; the API layer maps these to `503 Service Unavailable`.
- LanceDB operation errors surface as `500 Internal Server Error` with structured log output.
- MCP tool errors are returned as MCP error responses (not HTTP 500s).

**Logging**
- Structured JSON logging (stdlib `logging` + `python-json-logger`) with `request_id` and `bucket` fields on every log line.

**Phase 2 extension point**
- `SearchStrategy` ABC with a `search(bucket, query, memory_type, limit) -> list[MemoryRow]` method.
- `FtsSearchStrategy` (Phase 1) and `VectorSearchStrategy` (Phase 2) are bound in `StorageModule` — switching phases is a one-line Module change.

---

### Technology Choices

| Concern | Choice | Notes |
|---------|--------|-------|
| Web framework | **FastAPI** | Async, OpenAPI out of the box, integrates with MCP HTTP transport |
| MCP transport | **FastMCP** or **mcp[http]** | HTTP/SSE; no WebSocket needed |
| DI framework | **Injector** | Explicit, type-safe, testable; Google Guice style |
| Vector / FTS store | **LanceDB** | Embedded, file-based, works with BLOB sync pattern |
| DIAL SDK | **aidial-client** (`ai-dial-client-python`) | Bucket resolution, file upload/download |
| Settings | **Pydantic BaseSettings** | Env-var driven, validated at startup |
| Locking | **asyncio.Lock** (in-process) | Sufficient for Phase 1 single-instance deployment |

---

## Active Plan

⚠️ Architecture changed — @tech-lead must re-run to regenerate the plan.

---

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | **Sync concurrency** | Use **simple per-user file locking**. Only the authenticated user can access their bucket; concurrent requests from the same user are serialized with a local lock keyed on the user's bucket ID. |
| 2 | **DIAL Python SDK** | Use [`aidial-client`](https://github.com/epam/ai-dial-client-python) (`ai-dial-client-python`). It handles file upload/download (`client.files.*`), `my_files_home()` for bucket resolution, and per-request API key forwarding. Add to `pyproject.toml`. |
| 3 | **Episodic write ownership** | The **MCP server stores both `core` and `episodic` rows**. All write decisions belong to the orchestrating agent; the server is storage-only and accepts `store_memory` for either type without restriction. |
| 4 | **Embedding API (Phase 2)** | Use **DIAL Core's own embeddings endpoint** via `aidial-client`, forwarding the caller's per-request API key. The embedding model deployment name (e.g. `text-embedding-ada-002`) is declared in the Application Type schema and read at runtime via `request_dial_application_properties()`. The `embedding_model` column stores which model was used, enabling the cross-model safety guard (rows with a different model fall back to FTS). |
| 5 | **`applicationTypeViewerUrl` / `applicationTypeEditorUrl`** | Declare **placeholder values** in the Application Type schema for both `applicationTypeViewerUrl` (memory browser UI) and `applicationTypeEditorUrl` (configuration wizard). Custom UIs follow their own logic and are out of scope for this server. |
