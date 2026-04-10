"""Tests for LanceDbMemoryRepository.filter_by_context."""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.app.models.memory import MemoryRow
from src.app.storage.lance.repository import LanceDbMemoryRepository


def _make_repo(tmp_path: Path) -> LanceDbMemoryRepository:
    settings = MagicMock()
    settings.tmp_dir = tmp_path
    return LanceDbMemoryRepository(settings)


def _make_row(row_id: str, memory_type: str, context: str, importance: float = 0.5) -> MemoryRow:
    return MemoryRow(
        id=row_id,
        memory_type=memory_type,
        content=f"content for {row_id}",
        context=context,
        importance=importance,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        access_count=0,
    )


def test_filter_by_context_returns_matching_rows(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bucket = "test-bucket"
    row_match = _make_row("a1", "episodic", "my-app")
    row_other = _make_row("b2", "episodic", "other-app")
    repo.append(bucket, row_match)
    repo.append(bucket, row_other)

    results = repo.filter_by_context(bucket, "my-app", "episodic", limit=10)

    assert len(results) == 1
    assert results[0].id == "a1"


def test_filter_by_context_respects_memory_type(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bucket = "test-bucket"
    episodic = _make_row("e1", "episodic", "my-app")
    core = _make_row("c1", "core", "my-app")
    repo.append(bucket, episodic)
    repo.append(bucket, core)

    results = repo.filter_by_context(bucket, "my-app", "episodic", limit=10)

    ids = [r.id for r in results]
    assert "e1" in ids
    assert "c1" not in ids


def test_filter_by_context_respects_limit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bucket = "test-bucket"
    for i in range(5):
        repo.append(bucket, _make_row(f"r{i}", "episodic", "my-app"))

    results = repo.filter_by_context(bucket, "my-app", "episodic", limit=2)

    assert len(results) == 2


def test_filter_by_context_returns_empty_when_no_match(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    bucket = "test-bucket"
    repo.append(bucket, _make_row("x1", "episodic", "other-app"))

    results = repo.filter_by_context(bucket, "my-app", "episodic", limit=10)

    assert results == []
