# MCP Api-Key Header Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `api_key` from MCP tool parameters and instead read it from the `Api-Key` HTTP header via FastMCP's `Context`, matching how REST routes handle auth.

**Architecture:** FastMCP's streamable-HTTP transport attaches the Starlette `Request` to `ctx.request_context.request`. Tools declare `ctx: Context` as a parameter (injected automatically by FastMCP) and call `ctx.request_context.request.headers.get("Api-Key")`. If the header is absent, the tool returns an error dict with status 401. Tests mock `Context` via `patch.object`. Closes beads task: `ai-dial-memory-mcp-qzv`.

**Tech Stack:** Python 3.13, FastMCP (`mcp.server.fastmcp`), Starlette `Request`, pytest-asyncio

---

## File Map

### Modified
- `src/app/mcp/tools.py` — remove `api_key` params, add `ctx: Context`, extract header
- `src/tests/test_mcp_tools.py` — rewrite to mock Context instead of passing api_key
- `src/tests/test_mcp_tools_integration.py` — rewrite to mock Context instead of passing api_key

---

## Background: how Context carries HTTP headers

FastMCP's streamable-HTTP transport wraps each incoming POST in a Starlette `Request` and passes it through:

```
Starlette Request
  → StreamableHTTPServerTransport (ServerMessageMetadata.request_context = request)
  → lowlevel Server (RequestContext.request = request_data)
  → FastMCP.get_context() → Context(_request_context=RequestContext)
```

Inside a tool, access:
```python
api_key = ctx.request_context.request.headers.get("Api-Key")
```

`ctx.request_context.request` is `starlette.requests.Request` with a `.headers` mapping.

---

## Task 1: Write failing tests

- [ ] **Step 1: Write new unit tests in `test_mcp_tools.py`**

Replace the entire file with:
```python
"""Unit tests for MCP tools — store_memory and search_archive."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.models.memory import MemoryRow, StoreMemoryOutput
from src.app.mcp.tools import create_mcp_server


def _row(id: str) -> MemoryRow:
    return MemoryRow(
        id=id,
        memory_type="episodic",
        content="hello",
        context="ctx",
        importance=0.5,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        access_count=0,
    )


def _make_service() -> MagicMock:
    svc = MagicMock()
    svc.store = AsyncMock(return_value=StoreMemoryOutput(id="new-id", stored=True))
    svc.search_archive = AsyncMock(return_value=[_row("r1")])
    return svc


def _make_context(api_key: str = "test-key") -> MagicMock:
    """Build a mock FastMCP Context with Api-Key header."""
    request = MagicMock()
    request.headers = {"Api-Key": api_key}
    req_ctx = MagicMock()
    req_ctx.request = request
    ctx = MagicMock()
    ctx.request_context = req_ctx
    return ctx


@pytest.mark.asyncio
async def test_store_memory_reads_api_key_from_header() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    with patch.object(mcp, "get_context", return_value=_make_context("header-key")):
        result = await mcp.call_tool(
            "store_memory",
            {
                "content": "I like Python",
                "memory_type": "core",
                "context": "chat",
                "importance": 0.8,
            },
        )

    svc.store.assert_awaited_once()
    call_args = svc.store.call_args
    assert call_args.args[0] == "header-key"
    assert result is not None


@pytest.mark.asyncio
async def test_store_memory_returns_error_when_api_key_missing() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    ctx = MagicMock()
    ctx.request_context.request.headers = {}

    with patch.object(mcp, "get_context", return_value=ctx):
        result = await mcp.call_tool(
            "store_memory",
            {
                "content": "hello",
                "memory_type": "core",
                "context": "chat",
                "importance": 0.8,
            },
        )

    svc.store.assert_not_awaited()
    result_str = str(result)
    assert "401" in result_str or "Api-Key" in result_str


@pytest.mark.asyncio
async def test_search_archive_reads_api_key_from_header() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    with patch.object(mcp, "get_context", return_value=_make_context("search-key")):
        result = await mcp.call_tool(
            "search_archive",
            {"query": "Python"},
        )

    svc.search_archive.assert_awaited_once_with("search-key", "Python")
    assert result is not None


@pytest.mark.asyncio
async def test_search_archive_returns_error_when_api_key_missing() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    ctx = MagicMock()
    ctx.request_context.request.headers = {}

    with patch.object(mcp, "get_context", return_value=ctx):
        result = await mcp.call_tool("search_archive", {"query": "Python"})

    svc.search_archive.assert_not_awaited()
    result_str = str(result)
    assert "401" in result_str or "Api-Key" in result_str


@pytest.mark.asyncio
async def test_mcp_server_lists_both_tools() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    tools = await mcp.list_tools()
    names = {t.name for t in tools}

    assert "store_memory" in names
    assert "search_archive" in names


@pytest.mark.asyncio
async def test_store_memory_tool_schema_has_no_api_key_param() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    tools = await mcp.list_tools()
    store_tool = next(t for t in tools if t.name == "store_memory")
    param_names = set(store_tool.inputSchema.get("properties", {}).keys())
    assert "api_key" not in param_names


@pytest.mark.asyncio
async def test_search_archive_tool_schema_has_no_api_key_param() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    tools = await mcp.list_tools()
    search_tool = next(t for t in tools if t.name == "search_archive")
    param_names = set(search_tool.inputSchema.get("properties", {}).keys())
    assert "api_key" not in param_names
```

- [ ] **Step 2: Run to confirm new tests fail**

```bash
python -m pytest src/tests/test_mcp_tools.py -v
```
Expected: `FAILED` — tools still have `api_key` param so schema tests fail; `patch.object(mcp, "get_context")` tests fail because get_context isn't called yet.

---

## Task 2: Implement the fix in `tools.py`

- [ ] **Step 1: Rewrite `src/app/mcp/tools.py`**

```python
"""MCP tool registration via FastMCP (streamable HTTP transport)."""
from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from src.app.models.memory import MemoryType, StoreMemoryInput
from src.app.storage.common.memory_service import AbstractMemoryService


def _get_api_key(ctx: Context) -> str | None:
    """Extract Api-Key from the HTTP request headers."""
    return ctx.request_context.request.headers.get("Api-Key")


def create_mcp_server(service: AbstractMemoryService) -> FastMCP:
    mcp: FastMCP = FastMCP("ai-dial-memory")

    @mcp.tool()
    async def store_memory(
        content: str,
        memory_type: MemoryType,
        context: str,
        importance: float,
        ctx: Context,
    ) -> dict:
        """Store a new memory row."""
        api_key = _get_api_key(ctx)
        if not api_key:
            return {"error": "Api-Key header missing", "status": 401}
        try:
            result = await service.store(
                api_key,
                StoreMemoryInput(
                    content=content,
                    memory_type=memory_type,
                    context=context,
                    importance=importance,
                ),
            )
            return {"id": result.id, "stored": result.stored}
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool()
    async def search_archive(query: str, ctx: Context) -> list[dict]:
        """Full-text search over episodic memories."""
        api_key = _get_api_key(ctx)
        if not api_key:
            return [{"error": "Api-Key header missing", "status": 401}]
        try:
            rows = await service.search_archive(api_key, query)
            return [r.model_dump(mode="json") for r in rows]
        except Exception as exc:
            return [{"error": str(exc)}]

    return mcp
```

Note: `AbstractMemoryService` is used here. If the storage refactor plan (2026-04-06-storage-refactor.md) has not been applied yet, use `MemoryService` from `src.app.services.memory_service` and update after the refactor.

- [ ] **Step 2: Run new unit tests**

```bash
python -m pytest src/tests/test_mcp_tools.py -v
```
Expected: `7 passed`

---

## Task 3: Update integration tests

- [ ] **Step 1: Update `test_mcp_tools_integration.py`**

The integration tests call `mcp.call_tool("store_memory", {"api_key": "key", ...})`. After the fix, `api_key` is no longer a parameter. Replace the call arguments and mock the context.

Replace the two test functions:

```python
@pytest.mark.asyncio
async def test_store_memory_tool_persists_row_and_returns_id() -> None:
    repo = InMemoryRepository()
    svc = MemoryService(_make_sync(), repo)
    mcp = create_mcp_server(svc)

    ctx = MagicMock()
    ctx.request_context.request.headers = {"Api-Key": "key"}

    with patch.object(mcp, "get_context", return_value=ctx):
        result = await mcp.call_tool(
            "store_memory",
            {
                "content": "I prefer dark mode",
                "memory_type": "core",
                "context": "UI chat",
                "importance": 0.9,
            },
        )

    assert len(repo._rows) == 1
    stored = list(repo._rows.values())[0]
    assert stored.content == "I prefer dark mode"
    assert result is not None


@pytest.mark.asyncio
async def test_search_archive_tool_returns_matching_episodic_rows() -> None:
    repo = InMemoryRepository()
    repo._rows["e1"] = MemoryRow(
        id="e1",
        memory_type="episodic",
        content="went hiking in the Alps",
        context="travel",
        importance=0.6,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        access_count=0,
    )
    repo._rows["e2"] = MemoryRow(
        id="e2",
        memory_type="episodic",
        content="had coffee with Alice",
        context="social",
        importance=0.4,
        timestamp=datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc),
        access_count=0,
    )

    svc = MemoryService(_make_sync(), repo)
    mcp = create_mcp_server(svc)

    ctx = MagicMock()
    ctx.request_context.request.headers = {"Api-Key": "key"}

    with patch.object(mcp, "get_context", return_value=ctx):
        result = await mcp.call_tool("search_archive", {"query": "hiking"})

    assert result is not None
    result_str = str(result)
    assert "hiking" in result_str
```

Also add the `patch` import at the top:
```python
from unittest.mock import MagicMock, patch
```

- [ ] **Step 2: Run all MCP tests**

```bash
python -m pytest src/tests/test_mcp_tools.py src/tests/test_mcp_tools_integration.py -v
```
Expected: `9 passed`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest src/tests/ -v 2>&1 | tail -10
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/app/mcp/tools.py src/tests/test_mcp_tools.py src/tests/test_mcp_tools_integration.py
git commit -m "fix(mcp): read Api-Key from request header instead of tool parameter"
```

---

## Task 4: Close beads task and push

- [ ] **Step 1: Close the task**

```bash
bd close ai-dial-memory-mcp-qzv --reason="api_key removed from tool params; extracted from ctx.request_context.request.headers['Api-Key']; missing header returns {error, status:401}"
```

- [ ] **Step 2: Push**

```bash
git pull --rebase
bd dolt push
git push
```
