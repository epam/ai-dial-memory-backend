"""Tests for MemoryService.retrieve."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.models.memory import MemoryRow, RetrieveResponse
from src.app.storage.lance.memory_service import MemoryService


def _make_row(row_id: str, memory_type: str, context: str = "user", importance: float = 0.8) -> MemoryRow:
    return MemoryRow(
        id=row_id,
        memory_type=memory_type,
        content=f"content {row_id}",
        context=context,
        importance=importance,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        access_count=0,
    )


def _make_service() -> tuple[MemoryService, MagicMock, MagicMock]:
    sync = MagicMock()
    repo = MagicMock()
    # Make sync.open() work as async context manager yielding (None, "bucket-id")
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=(None, "bucket-id"))
    cm.__aexit__ = AsyncMock(return_value=False)
    sync.open.return_value = cm
    return MemoryService(sync, repo), sync, repo


@pytest.mark.asyncio
async def test_retrieve_without_app_name_returns_only_core() -> None:
    service, _, repo = _make_service()
    core_row = _make_row("c1", "core")
    repo.top_by_importance.return_value = [core_row]

    result = await service.retrieve("api-key", app_name=None)

    assert isinstance(result, RetrieveResponse)
    assert len(result.facts) == 1
    assert result.facts[0].id == "c1"
    repo.filter_by_context.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_with_app_name_returns_core_and_episodic() -> None:
    service, _, repo = _make_service()
    core_row = _make_row("c1", "core")
    episodic_row = _make_row("e1", "episodic", context="my-app")
    repo.top_by_importance.return_value = [core_row]
    repo.filter_by_context.return_value = [episodic_row]

    result = await service.retrieve("api-key", app_name="my-app")

    assert len(result.facts) == 2
    ids = [r.id for r in result.facts]
    assert "c1" in ids
    assert "e1" in ids
    repo.filter_by_context.assert_called_once_with("bucket-id", "my-app", "episodic", 10)


@pytest.mark.asyncio
async def test_retrieve_deduplicates_by_id_tier1_wins() -> None:
    service, _, repo = _make_service()
    row = _make_row("shared", "core", importance=0.9)
    repo.top_by_importance.return_value = [row]
    # Same id appears in episodic results too
    repo.filter_by_context.return_value = [_make_row("shared", "episodic", importance=0.3)]

    result = await service.retrieve("api-key", app_name="my-app")

    assert len(result.facts) == 1
    assert result.facts[0].importance == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_retrieve_passes_tier_limits() -> None:
    service, _, repo = _make_service()
    repo.top_by_importance.return_value = []
    repo.filter_by_context.return_value = []

    await service.retrieve("api-key", app_name="my-app", tier1_limit=3, tier2_limit=7)

    repo.top_by_importance.assert_called_once_with("bucket-id", "core", 3)
    repo.filter_by_context.assert_called_once_with("bucket-id", "my-app", "episodic", 7)
