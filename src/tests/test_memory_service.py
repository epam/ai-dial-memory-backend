"""Unit tests for MemoryService — delegation, dedup, and Tier1-before-Tier2 ordering."""
from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.app.models.memory import MemoryRow, StoreMemoryInput
from src.app.storage.common.errors import RowNotFoundError
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(id: str, memory_type: str = "core", importance: float = 0.5) -> MemoryRow:
    return MemoryRow(
        id=id,
        memory_type=memory_type,  # type: ignore[arg-type]
        content=f"content-{id}",
        context="ctx",
        importance=importance,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        access_count=0,
    )


def _make_sync(bucket_id: str = "bucket-abc") -> MagicMock:
    sync = MagicMock()

    @asynccontextmanager
    async def _open(api_key: str, *, write: bool):  # noqa: ANN001
        yield Path("/tmp/fake"), bucket_id

    sync.open = _open
    return sync


# ---------------------------------------------------------------------------
# store()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_appends_row_and_returns_stored_true() -> None:
    repo = MagicMock()
    svc = MemoryService(_make_sync(), repo)

    result = await svc.store(
        "key",
        StoreMemoryInput(content="hello", memory_type="core", context="ctx", importance=0.8),
    )

    repo.append.assert_called_once()
    assert result.stored is True
    assert result.id  # non-empty id


# ---------------------------------------------------------------------------
# retrieve() — ordering and deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_tier1_rows_appear_before_tier2_rows() -> None:
    t1 = _row("t1", "core", importance=0.9)
    t2 = _row("t2", "episodic", importance=0.3)

    repo = MagicMock()
    repo.top_by_importance = MagicMock(return_value=[t1])
    repo.fts_search = MagicMock(return_value=[t2])

    svc = MemoryService(_make_sync(), repo)
    result = await svc.retrieve("key", "query", tier1_limit=5, tier2_limit=10)

    assert [r.id for r in result.facts] == ["t1", "t2"]


@pytest.mark.asyncio
async def test_retrieve_deduplicates_by_id_keeping_tier1_copy() -> None:
    shared = _row("dup", "core", importance=0.8)
    dup_in_tier2 = _row("dup", "episodic", importance=0.1)
    unique = _row("unique", "episodic", importance=0.2)

    repo = MagicMock()
    repo.top_by_importance = MagicMock(return_value=[shared])
    repo.fts_search = MagicMock(return_value=[dup_in_tier2, unique])

    svc = MemoryService(_make_sync(), repo)
    result = await svc.retrieve("key", "query", tier1_limit=5, tier2_limit=10)

    ids = [r.id for r in result.facts]
    assert ids.count("dup") == 1
    assert ids.index("dup") < ids.index("unique")
    # The surviving copy is the Tier1 row
    assert result.facts[0].memory_type == "core"


# ---------------------------------------------------------------------------
# search_archive()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_archive_delegates_to_fts_search() -> None:
    rows = [_row("e1", "episodic")]
    repo = MagicMock()
    repo.fts_search = MagicMock(return_value=rows)

    svc = MemoryService(_make_sync("bkt"), repo)
    result = await svc.search_archive("key", "some query")

    repo.fts_search.assert_called_once_with("bkt", "some query", "episodic", 20)
    assert result == rows


# ---------------------------------------------------------------------------
# list_rows()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_rows_delegates_with_optional_filter() -> None:
    rows = [_row("r1")]
    repo = MagicMock()
    repo.list_rows = MagicMock(return_value=rows)

    svc = MemoryService(_make_sync("bkt"), repo)
    result = await svc.list_rows("key", memory_type="core")

    repo.list_rows.assert_called_once_with("bkt", "core")
    assert result == rows


# ---------------------------------------------------------------------------
# get_row()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_row_returns_row_when_found() -> None:
    row = _row("r1")
    repo = MagicMock()
    repo.get = MagicMock(return_value=row)

    svc = MemoryService(_make_sync("bkt"), repo)
    result = await svc.get_row("key", "r1")

    assert result is row
    repo.get.assert_called_once_with("bkt", "r1")


@pytest.mark.asyncio
async def test_get_row_raises_when_not_found() -> None:
    repo = MagicMock()
    repo.get = MagicMock(return_value=None)

    svc = MemoryService(_make_sync(), repo)

    with pytest.raises(RowNotFoundError):
        await svc.get_row("key", "missing-id")


# ---------------------------------------------------------------------------
# delete_row()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_row_calls_repo_delete() -> None:
    row = _row("r1")
    repo = MagicMock()
    repo.get = MagicMock(return_value=row)
    repo.delete = MagicMock()

    svc = MemoryService(_make_sync("bkt"), repo)
    await svc.delete_row("key", "r1")

    repo.delete.assert_called_once_with("bkt", "r1")


@pytest.mark.asyncio
async def test_delete_row_raises_when_not_found() -> None:
    repo = MagicMock()
    repo.get = MagicMock(return_value=None)

    svc = MemoryService(_make_sync(), repo)

    with pytest.raises(RowNotFoundError):
        await svc.delete_row("key", "missing-id")


def test_abstract_memory_service_is_abstract() -> None:
    import inspect
    assert inspect.isabstract(AbstractMemoryService)
    abstract_methods = {
        "store", "search_archive", "retrieve", "list_rows", "get_row", "delete_row"
    }
    assert AbstractMemoryService.__abstractmethods__ == abstract_methods


def test_memory_service_implements_abstract_interface() -> None:
    assert issubclass(MemoryService, AbstractMemoryService)
