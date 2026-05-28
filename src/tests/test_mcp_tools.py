"""Unit tests for MCP tools — store_memory and search_archive."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.mcp.tools import create_mcp_server
from src.app.models.memory import MemoryRow, RetrieveResponse, StoreMemoryOutput


def _row(id: str) -> MemoryRow:
    return MemoryRow(
        id=id,
        memory_type="episodic",
        content="hello",
        context="ctx",
        importance=0.5,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
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
    assert "get_skill" in names


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


# ---------------------------------------------------------------------------
# prime_memories and get_skill tools
# ---------------------------------------------------------------------------

def _make_prime_ctx(api_key: str | None) -> MagicMock:
    """Build a mock FastMCP Context for prime_memories (headers.get() style)."""
    ctx = MagicMock()
    ctx.request_context.request.headers.get.return_value = api_key
    return ctx


def _make_prime_row(row_id: str) -> MemoryRow:
    import datetime
    return MemoryRow(
        id=row_id,
        memory_type="core",
        content="a fact",
        context="user",
        importance=0.9,
        timestamp=datetime.datetime.now(tz=datetime.UTC),
        access_count=0,
    )


def _get_tool_fn(mcp, name: str):  # type: ignore[no-untyped-def]
    return next(
        (t for t in mcp._tool_manager._tools.values() if t.name == name),
        None,
    )


@pytest.mark.asyncio
async def test_prime_memories_returns_facts() -> None:
    service = MagicMock()
    service.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[_make_prime_row("r1")]))
    mcp = create_mcp_server(service)

    tool_fn = _get_tool_fn(mcp, "prime_memories")
    assert tool_fn is not None, "prime_memories tool not registered"
    result = await tool_fn.fn(app_name="my-app", ctx=_make_prime_ctx("test-key"))

    assert isinstance(result, list)
    assert result[0]["id"] == "r1"
    service.retrieve.assert_awaited_once_with("test-key", "my-app")


@pytest.mark.asyncio
async def test_prime_memories_missing_api_key_returns_error() -> None:
    service = MagicMock()
    mcp = create_mcp_server(service)

    tool_fn = _get_tool_fn(mcp, "prime_memories")
    assert tool_fn is not None, "prime_memories tool not registered"
    result = await tool_fn.fn(app_name="my-app", ctx=_make_prime_ctx(None))

    assert result[0]["status"] == 401
    service.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_prime_memories_none_app_name_passes_through() -> None:
    service = MagicMock()
    service.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[]))
    mcp = create_mcp_server(service)

    tool_fn = _get_tool_fn(mcp, "prime_memories")
    assert tool_fn is not None, "prime_memories tool not registered"
    await tool_fn.fn(app_name=None, ctx=_make_prime_ctx("test-key"))

    service.retrieve.assert_awaited_once_with("test-key", None)


@pytest.mark.asyncio
async def test_get_skill_returns_instructions() -> None:
    from src.app.mcp.skill import SKILL_INSTRUCTIONS

    mcp = create_mcp_server(MagicMock())
    tool_fn = _get_tool_fn(mcp, "get_skill")
    assert tool_fn is not None, "get_skill tool not registered"
    result = await tool_fn.fn()

    assert result == SKILL_INSTRUCTIONS


@pytest.mark.asyncio
async def test_get_skill_listed_in_tools() -> None:
    mcp = create_mcp_server(MagicMock())
    tools = await mcp.list_tools()
    assert "get_skill" in {t.name for t in tools}
