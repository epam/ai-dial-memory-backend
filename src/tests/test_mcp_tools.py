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
