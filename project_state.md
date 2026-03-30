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

The server MUST expose an endpoint that quickapps-backend calls before each agent turn to retrieve core facts for injection into the system prompt:

- **Tier 1** — top-N core facts by importance (always injected).
- **Tier 2** — core facts matching the current user message (FTS in Phase 1, vector search in Phase 2), scored as `importance`-weighted relevance.
- Both tiers are merged and deduplicated by `id` before returning.

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

> To be filled by **@architect**

---

## Active Plan

> To be filled by **@tech-lead**

---

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | **Sync concurrency** | Use **simple per-user file locking**. Only the authenticated user can access their bucket; concurrent requests from the same user are serialized with a local lock keyed on the user's bucket ID. |
| 2 | **DIAL Python SDK** | Use [`aidial-client`](https://github.com/epam/ai-dial-client-python) (`ai-dial-client-python`). It handles file upload/download (`client.files.*`), `my_files_home()` for bucket resolution, and bearer token forwarding. Add to `pyproject.toml`. |
| 3 | **Episodic write ownership** | The **MCP server stores both `core` and `episodic` rows**. All write decisions belong to the orchestrating agent; the server is storage-only and accepts `store_memory` for either type without restriction. |
| 4 | **Embedding API (Phase 2)** | Use **DIAL Core's own embeddings endpoint** via `aidial-client`, forwarding the caller's bearer token. The embedding model deployment name (e.g. `text-embedding-ada-002`) is declared in the Application Type schema and read at runtime via `request_dial_application_properties()`. The `embedding_model` column stores which model was used, enabling the cross-model safety guard (rows with a different model fall back to FTS). |
| 5 | **`applicationTypeViewerUrl` / `applicationTypeEditorUrl`** | Declare **placeholder values** in the Application Type schema for both `applicationTypeViewerUrl` (memory browser UI) and `applicationTypeEditorUrl` (configuration wizard). Custom UIs follow their own logic and are out of scope for this server. |
