"""Tests for MCP tools — prime_memories."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.mcp.tools import create_mcp_server
from src.app.models.memory import MemoryRow, RetrieveResponse


def _make_row(row_id: str) -> MemoryRow:
    return MemoryRow(
        id=row_id,
        memory_type="core",
        content="a fact",
        context="user",
        importance=0.9,
        timestamp=datetime.datetime.now(tz=datetime.UTC),
        access_count=0,
    )


def _make_context(api_key: str | None) -> MagicMock:
    ctx = MagicMock()
    ctx.request_context.request.headers.get.return_value = api_key
    return ctx


@pytest.mark.asyncio
async def test_prime_memories_returns_facts() -> None:
    service = MagicMock()
    service.retrieve = AsyncMock(
        return_value=RetrieveResponse(facts=[_make_row("r1")])
    )
    mcp = create_mcp_server(service)

    # Access the tool function directly
    tool_fn = next(
        (t for t in mcp._tool_manager._tools.values() if t.name == "prime_memories"),
        None,
    )
    assert tool_fn is not None, "prime_memories tool not registered"
    ctx = _make_context("test-key")
    result = await tool_fn.fn(app_name="my-app", ctx=ctx)

    assert isinstance(result, list)
    assert result[0]["id"] == "r1"
    service.retrieve.assert_awaited_once_with("test-key", "my-app")


@pytest.mark.asyncio
async def test_prime_memories_missing_api_key_returns_error() -> None:
    service = MagicMock()
    mcp = create_mcp_server(service)

    tool_fn = next(
        (t for t in mcp._tool_manager._tools.values() if t.name == "prime_memories"),
        None,
    )
    assert tool_fn is not None, "prime_memories tool not registered"
    ctx = _make_context(None)
    result = await tool_fn.fn(app_name="my-app", ctx=ctx)

    assert result[0]["status"] == 401
    service.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_prime_memories_none_app_name_passes_through() -> None:
    service = MagicMock()
    service.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[]))
    mcp = create_mcp_server(service)

    tool_fn = next(
        (t for t in mcp._tool_manager._tools.values() if t.name == "prime_memories"),
        None,
    )
    assert tool_fn is not None, "prime_memories tool not registered"
    ctx = _make_context("test-key")
    await tool_fn.fn(app_name=None, ctx=ctx)

    service.retrieve.assert_awaited_once_with("test-key", None)


@pytest.mark.asyncio
async def test_get_skill_returns_instructions() -> None:
    from src.app.mcp.skill import SKILL_INSTRUCTIONS

    service = MagicMock()
    mcp = create_mcp_server(service)

    tool_fn = next(
        (t for t in mcp._tool_manager._tools.values() if t.name == "get_skill"),
        None,
    )
    assert tool_fn is not None, "get_skill tool not registered"
    result = await tool_fn.fn()

    assert result == SKILL_INSTRUCTIONS


@pytest.mark.asyncio
async def test_get_skill_listed_in_tools() -> None:
    service = MagicMock()
    mcp = create_mcp_server(service)

    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "get_skill" in names
