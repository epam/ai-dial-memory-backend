"""Tests for centralized exception handler — consistent JSON message shape."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from injector import Injector, Module, provider, singleton

from src.app.api.router import create_api_router
from src.app.dial.dial_storage import DialStorageService
from src.app.services.memory_service import MemoryService, RowNotFoundError
from src.app.storage.sync import StorageSyncError


def _make_app(svc: MagicMock) -> object:
    dial = MagicMock()
    dial.get_storage_home = AsyncMock(return_value="files/bucket")

    class TestModule(Module):
        @provider
        @singleton
        def provide_svc(self) -> MemoryService:
            return svc  # type: ignore[return-value]

        @provider
        @singleton
        def provide_dial(self) -> DialStorageService:
            return dial  # type: ignore[return-value]

    return create_api_router(Injector([TestModule()]))


@pytest.mark.asyncio
async def test_row_not_found_returns_404_with_message_field() -> None:
    svc = MagicMock()
    svc.get_row = AsyncMock(side_effect=RowNotFoundError("Row not found"))

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc)), base_url="http://test"
    ) as c:
        r = await c.get("/memory/missing", headers={"Api-Key": "k"})

    assert r.status_code == 404
    body = r.json()
    assert "message" in body
    assert "detail" not in body


@pytest.mark.asyncio
async def test_storage_sync_error_returns_503_with_message_field() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(side_effect=StorageSyncError("dial down"))

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc)), base_url="http://test"
    ) as c:
        r = await c.get("/memory", headers={"Api-Key": "k"})

    assert r.status_code == 503
    assert "message" in r.json()


@pytest.mark.asyncio
async def test_unhandled_error_returns_500_with_message_field() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(side_effect=RuntimeError("unexpected"))

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc)), base_url="http://test"
    ) as c:
        r = await c.get("/memory", headers={"Api-Key": "k"})

    assert r.status_code == 500
    assert "message" in r.json()
