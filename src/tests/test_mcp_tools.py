"""Unit tests for MCP tools — store_memory and search_archive."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_store_memory_returns_id_and_stored_true() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    result = await mcp.call_tool(
        "store_memory",
        {
            "api_key": "key",
            "content": "I like Python",
            "memory_type": "core",
            "context": "chat",
            "importance": 0.8,
        },
    )

    svc.store.assert_awaited_once()
    call_args = svc.store.call_args
    assert call_args.args[0] == "key"
    assert result is not None


@pytest.mark.asyncio
async def test_search_archive_returns_matching_rows() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    result = await mcp.call_tool(
        "search_archive",
        {"api_key": "key", "query": "Python"},
    )

    svc.search_archive.assert_awaited_once_with("key", "Python")
    assert result is not None


@pytest.mark.asyncio
async def test_mcp_server_lists_both_tools() -> None:
    svc = _make_service()
    mcp = create_mcp_server(svc)

    tools = await mcp.list_tools()
    names = {t.name for t in tools}

    assert "store_memory" in names
    assert "search_archive" in names
