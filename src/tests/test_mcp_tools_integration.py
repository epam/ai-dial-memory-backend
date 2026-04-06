"""Integration tests for MCP tools against a real MemoryService."""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.app.models.memory import MemoryRow, MemoryType
from src.app.storage.common.repository import MemoryRepository
from src.app.storage.lance.memory_service import MemoryService
from src.app.mcp.tools import create_mcp_server


# ---------------------------------------------------------------------------
# In-memory MemoryRepository for integration tests
# ---------------------------------------------------------------------------

class InMemoryRepository(MemoryRepository):
    def __init__(self) -> None:
        self._rows: dict[str, MemoryRow] = {}

    def append(self, bucket: str, row: MemoryRow) -> None:
        self._rows[row.id] = row

    def get(self, bucket: str, row_id: str) -> MemoryRow | None:
        return self._rows.get(row_id)

    def list_rows(self, bucket: str, memory_type: MemoryType | None = None) -> list[MemoryRow]:
        rows = list(self._rows.values())
        if memory_type is not None:
            rows = [r for r in rows if r.memory_type == memory_type]
        return rows

    def delete(self, bucket: str, row_id: str) -> None:
        self._rows.pop(row_id, None)

    def fts_search(self, bucket: str, query: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]:
        return [
            r for r in self._rows.values()
            if r.memory_type == memory_type and query.lower() in r.content.lower()
        ][:limit]

    def top_by_importance(self, bucket: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]:
        rows = [r for r in self._rows.values() if r.memory_type == memory_type]
        return sorted(rows, key=lambda r: r.importance, reverse=True)[:limit]


def _make_context(api_key: str = "key") -> MagicMock:
    """Build a mock FastMCP Context with Api-Key header."""
    request = MagicMock()
    request.headers = {"Api-Key": api_key}
    req_ctx = MagicMock()
    req_ctx.request = request
    ctx = MagicMock()
    ctx.request_context = req_ctx
    return ctx


def _make_sync() -> MagicMock:
    sync = MagicMock()

    @asynccontextmanager
    async def _open(api_key: str, *, write: bool):  # noqa: ANN001
        yield Path("/tmp/fake"), "test-bucket"

    sync.open = _open
    return sync


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_memory_tool_persists_row_and_returns_id() -> None:
    repo = InMemoryRepository()
    svc = MemoryService(_make_sync(), repo)
    mcp = create_mcp_server(svc)

    with patch.object(mcp, "get_context", return_value=_make_context("key")):
        result = await mcp.call_tool(
            "store_memory",
            {
                "content": "I prefer dark mode",
                "memory_type": "core",
                "context": "UI chat",
                "importance": 0.9,
            },
        )

    # Row was stored
    assert len(repo._rows) == 1
    stored = list(repo._rows.values())[0]
    assert stored.content == "I prefer dark mode"

    # Tool returned a result (not an error)
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

    with patch.object(mcp, "get_context", return_value=_make_context("key")):
        result = await mcp.call_tool("search_archive", {"query": "hiking"})

    assert result is not None
    # The result content should reference the hiking row
    result_str = str(result)
    assert "hiking" in result_str
