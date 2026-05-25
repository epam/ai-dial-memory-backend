"""Unit tests for LanceDbMemoryRepository with lancedb mocked (no Windows wheel)."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.app.config.app_settings import AppSettings
from src.app.models.memory import MemoryRow
from src.app.storage.lance.repository import LanceDbMemoryRepository


def _row_dict(rid: str = "rid-1", importance: float = 0.5) -> dict:
    return {
        "id": rid,
        "memory_type": "core",
        "content": "hello",
        "context": "ctx",
        "importance": importance,
        "embedding_model": None,
        "vector": None,
        "timestamp": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        "access_count": 0,
    }


def _fake_df(records: list[dict]) -> MagicMock:
    m = MagicMock()
    m.empty = len(records) == 0

    def to_dict(orient: str) -> list[dict]:
        assert orient == "records"
        return list(records)

    m.to_dict.side_effect = to_dict
    sorted_recs = sorted(records, key=lambda r: float(r["importance"]), reverse=True)
    sorted_m = MagicMock()
    sorted_m.empty = len(sorted_recs) == 0
    sorted_m.to_dict.side_effect = lambda orient: (
        list(sorted_recs) if orient == "records" else []
    )
    m.sort_values.return_value = sorted_m
    return m


def _query_chain(df: MagicMock) -> MagicMock:
    q = MagicMock()
    q.where.return_value = q
    q.limit.return_value = q
    q.to_pandas.return_value = df
    return q


@pytest.fixture
def settings(tmp_path) -> AppSettings:
    return AppSettings(DIAL_URL="http://dial", TMP_DIR=tmp_path)


def test_append_creates_table_and_adds_row(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = []
    db.create_table.return_value = table

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        row = MemoryRow.model_validate(_row_dict())
        repo.append("bucket-a", row)

    db.create_table.assert_called_once()
    table.add.assert_called_once()
    args, _kw = table.add.call_args
    assert args[0][0]["id"] == "rid-1"


def test_list_rows_applies_memory_type_filter(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    records = [_row_dict("1"), _row_dict("2")]
    chain = _query_chain(_fake_df(records))
    table.search.return_value = chain

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        out = repo.list_rows("bucket-a", memory_type="core")

    assert len(out) == 2
    chain.where.assert_called_once()


def test_delete_calls_table_delete(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    table.search.return_value = _query_chain(_fake_df([]))

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        repo.delete("bucket-a", "x-1")

    table.delete.assert_called_once_with("id = 'x-1'")


def test_get_returns_none_when_empty(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    df = _fake_df([])
    df.empty = True
    table.search.return_value = _query_chain(df)

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        assert repo.get("bucket-a", "missing") is None


def test_fts_search_uses_query_type_fts(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    rec = _row_dict()
    chain = _query_chain(_fake_df([rec]))
    table.search.return_value = chain

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        out = repo.fts_search("b", "needle", "core", limit=5)

    table.search.assert_called()
    first_call = table.search.call_args_list[0]
    assert first_call[0][0] == "needle"
    assert first_call[1].get("query_type") == "fts"
    assert len(out) == 1
    assert out[0].id == "rid-1"


def test_top_by_importance_sorts_descending(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    r_low = _row_dict("low", importance=0.1)
    r_high = _row_dict("high", importance=0.9)
    df = _fake_df([r_low, r_high])
    table.search.return_value = _query_chain(df)

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        out = repo.top_by_importance("b", "core", limit=10)

    df.sort_values.assert_called_once()
    assert out[0].id == "high"
    assert out[1].id == "low"


def test_delete_escapes_single_quote_in_row_id(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    table.search.return_value = _query_chain(_fake_df([]))

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        repo.delete("bucket-a", "foo'bar")

    table.delete.assert_called_once_with("id = 'foo''bar'")


def test_filter_by_context_escapes_single_quote(settings: AppSettings) -> None:
    table = MagicMock()
    db = MagicMock()
    db.table_names.return_value = ["memory"]
    db.open_table.return_value = table
    chain = _query_chain(_fake_df([]))
    table.search.return_value = chain

    with patch("src.app.storage.lance.repository.lancedb.connect", return_value=db):
        repo = LanceDbMemoryRepository(settings)
        repo.filter_by_context("bucket-a", "O'Brien", "episodic", limit=5)

    call_args = chain.where.call_args[0][0]
    assert "O''Brien" in call_args
