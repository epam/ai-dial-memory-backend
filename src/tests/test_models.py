"""Unit tests for app.models.memory domain models."""

from __future__ import annotations

import datetime
import json

import pytest
from pydantic import ValidationError

from src.app.models.memory import (
    MemoryRow,
    RetrieveRequest,
    RetrieveResponse,
    StoreMemoryInput,
)


def test_store_memory_input_importance_too_high_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        StoreMemoryInput(
            content="c",
            memory_type="core",
            context="ctx",
            importance=1.5,
        )
    assert "importance" in str(exc.value).lower()


def test_store_memory_input_importance_negative_raises() -> None:
    with pytest.raises(ValidationError):
        StoreMemoryInput(
            content="c",
            memory_type="core",
            context="ctx",
            importance=-0.1,
        )


@pytest.mark.parametrize("imp", [0.0, 1.0, 0.5])
def test_store_memory_input_importance_bounds_accepted(imp: float) -> None:
    m = StoreMemoryInput(
        content="c",
        memory_type="core",
        context="ctx",
        importance=imp,
    )
    assert m.importance == imp


def test_memory_row_json_round_trip() -> None:
    ts = datetime.datetime(
        2026, 3, 31, 12, 30, 45, tzinfo=datetime.UTC
    )
    row = MemoryRow(
        id="uuid-1",
        memory_type="core",
        content="hello",
        context="prefs",
        importance=0.7,
        embedding_model=None,
        vector=None,
        timestamp=ts,
        access_count=3,
    )
    dumped = row.model_dump_json()
    loaded = MemoryRow.model_validate_json(dumped)
    assert loaded == row


def test_retrieve_response_default_facts_are_independent() -> None:
    a = RetrieveResponse()
    b = RetrieveResponse()
    assert a.facts == []
    assert b.facts == []
    assert a.facts is not b.facts
    a.facts.append(
        MemoryRow(
            id="x",
            memory_type="core",
            content="c",
            context="k",
            importance=0.1,
            timestamp=datetime.datetime.now(datetime.UTC),
            access_count=0,
        )
    )
    assert b.facts == []


def test_store_memory_input_invalid_memory_type_raises() -> None:
    with pytest.raises(ValidationError):
        StoreMemoryInput(
            content="c",
            memory_type="invalid",  # type: ignore[arg-type]
            context="ctx",
            importance=0.5,
        )


@pytest.mark.parametrize("mt", ["core", "episodic"])
def test_store_memory_input_valid_memory_types(mt: str) -> None:
    m = StoreMemoryInput(
        content="c",
        memory_type=mt,  # type: ignore[arg-type]
        context="ctx",
        importance=0.5,
    )
    assert m.memory_type == mt


def test_retrieve_request_defaults() -> None:
    r = RetrieveRequest()
    assert r.tier1_limit == 5
    assert r.tier2_limit == 10


def test_memory_row_round_trip_preserves_timestamp_in_json_dict() -> None:
    ts = datetime.datetime(
        2026, 1, 15, 8, 0, 0, 123456, tzinfo=datetime.UTC
    )
    row = MemoryRow(
        id="id-2",
        memory_type="episodic",
        content="ev",
        context="c",
        importance=0.2,
        timestamp=ts,
        access_count=1,
    )
    payload = json.loads(row.model_dump_json())
    assert "timestamp" in payload
    loaded = MemoryRow.model_validate(payload)
    assert loaded.timestamp == ts


def test_retrieve_request_defaults_app_name_to_none() -> None:
    req = RetrieveRequest()
    assert req.app_name is None
    assert req.tier1_limit == 5
    assert req.tier2_limit == 10


def test_retrieve_request_accepts_app_name() -> None:
    req = RetrieveRequest(app_name="my-dial-app")
    assert req.app_name == "my-dial-app"
