"""Tests for GET /memory/retrieve."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.retrieve_router import make_retrieve_router
from src.app.config.application import MemoryAppConfig
from src.app.middleware.auth import UserContext
from src.app.models.memory import MemoryRow, RetrieveResponse


def _make_row(row_id: str) -> MemoryRow:
    return MemoryRow(
        id=row_id,
        memory_type="core",
        content="a fact",
        context="user",
        importance=0.9,
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        access_count=0,
    )


def _make_client(service_retrieve_return: RetrieveResponse) -> tuple[TestClient, AsyncMock]:
    service = MagicMock()
    service.retrieve = AsyncMock(return_value=service_retrieve_return)

    app = FastAPI()
    router = make_retrieve_router(
        service=service,
        user_context_dep=lambda: UserContext(api_key="test-key"),
        app_config_dep=lambda: MemoryAppConfig(tier1_limit=5, tier2_limit=10),
    )
    app.include_router(router)
    return TestClient(app), service.retrieve


def test_retrieve_with_app_name_calls_service() -> None:
    expected = RetrieveResponse(facts=[_make_row("r1")])
    client, mock_retrieve = _make_client(expected)

    response = client.get("/memory/retrieve", params={"app_name": "my-app"})

    assert response.status_code == 200
    mock_retrieve.assert_awaited_once_with("test-key", "my-app", 5, 10)


def test_retrieve_without_app_name_passes_none() -> None:
    expected = RetrieveResponse(facts=[_make_row("r1")])
    client, mock_retrieve = _make_client(expected)

    response = client.get("/memory/retrieve")

    assert response.status_code == 200
    mock_retrieve.assert_awaited_once_with("test-key", None, 5, 10)


def test_retrieve_returns_facts_in_response() -> None:
    expected = RetrieveResponse(facts=[_make_row("abc")])
    client, _ = _make_client(expected)

    response = client.get("/memory/retrieve", params={"app_name": "x"})

    data = response.json()
    assert data["facts"][0]["id"] == "abc"
