# Design: `prime_memories` MCP Tool + Retrieve Endpoint Refactor

**Date:** 2026-04-10
**Status:** Approved

## Problem

The existing `GET /memory/retrieve?query=...` endpoint requires the caller to supply a free-text query for FTS search over episodic memories. This is awkward for a synthetic (automatic) tool call at the start of every dialogue — the agent has no natural query at that point. There is also no MCP-level retrieve tool; retrieve is REST-only.

## Goal

1. Add a `prime_memories` MCP tool designed to be injected as a synthetic tool call at the start of every dialogue. It returns the most important core memories plus episodic memories scoped to the calling app/deployment — giving the agent its full context before the first user turn.
2. Refactor `GET /memory/retrieve` to use the same `app_name`-based logic, replacing the `?query=` parameter.

## Design

### Linking Mechanism

The `context` field on `MemoryRow` (already present in the schema) is the link between stored memories and the app that owns them. `SKILL.md` will be updated to require that the deployment/app name is always set as `context` when storing episodic memories.

### Retrieval Logic (shared by tool and REST endpoint)

| Tier | What | Condition |
|------|------|-----------|
| Tier 1 | Top-N `core` memories ordered by `importance DESC` | Always |
| Tier 2 | Episodic memories filtered by `context = app_name` | Only when `app_name` is provided |

When `app_name` is `None`, only Tier 1 (core memories) is returned.

Results are merged and deduplicated by `id`; Tier 1 wins on conflict. Returns `RetrieveResponse { facts: list[MemoryRow] }`.

Tier limits remain configurable via `X-Dial-Application-Properties` header (`tier1_limit`, `tier2_limit`), defaulting to 5 and 10.

### `prime_memories` MCP Tool

```
tool: prime_memories
parameter: app_name: str | None = None
reads: Api-Key header (same as other tools)
returns: RetrieveResponse
```

Designed as a synthetic tool call — injected automatically by the DIAL runtime at the start of every dialogue, not triggered by the user.

### REST Endpoint

`GET /memory/retrieve?app_name=<name>` replaces `GET /memory/retrieve?query=<text>`.

`app_name` is an optional query parameter. Behaviour when absent: Tier 1 only.

### Service Layer

`MemoryService.retrieve(api_key, app_name: str | None)` replaces the old `retrieve(api_key, request: RetrieveRequest)` where `RetrieveRequest` held a `query` string. FTS path is removed entirely.

### Repository Layer

New method: `filter_by_context(bucket, context: str, memory_type: str, limit: int) -> list[MemoryRow]`

Replaces the existing `fts_search` call in the retrieve path. Uses an exact-match filter on the `context` column (LanceDB `.filter()` predicate).

## Files to Change

| File | Change |
|------|--------|
| `src/app/mcp/tools.py` | Add `prime_memories` tool |
| `src/app/storage/lance/memory_service.py` | Refactor `retrieve`: remove query/FTS, accept `app_name: str \| None` |
| `src/app/storage/lance/repository.py` | Add `filter_by_context` method |
| `src/app/api/retrieve_router.py` | Swap `query` param for `app_name` |
| `src/app/models/memory.py` | Update `RetrieveRequest`: replace `query: str` with `app_name: str \| None` |
| `SKILL.md` | Add rule: episodic memories MUST set `context` to the deployment/app name |

## Out of Scope

- Schema changes to `MemoryRow` (no new fields; `context` field is reused)
- Migration of existing memories (tracked separately in `ai-dial-memory-mcp-26k`)
- Changes to `store_memory` or `search_archive` tools
- Fallback to `context = "user"` episodic memories when `app_name` is provided
