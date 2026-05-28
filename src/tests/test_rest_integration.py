"""Full integration tests for REST routes through create_api_router + real auth."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from injector import Injector, Module, provider, singleton

from src.app.api.router import create_api_router
from src.app.dial.dial_storage import DialStorageService
from src.app.models.memory import MemoryRow
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
from src.app.storage.common.memory_service import AbstractMemoryService


def _row(id: str = "r1") -> MemoryRow:
    return MemoryRow(
        id=id,
        memory_type="core",
        content="content",
        context="ctx",
        importance=0.9,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        access_count=0,
    )


def _make_app(svc: MagicMock, dial: MagicMock) -> FastAPI:  # type: ignore[misc]
    class TestModule(Module):
        @provider
        @singleton
        def provide_svc(self) -> AbstractMemoryService:
            return svc  # type: ignore[return-value]

        @provider
        @singleton
        def provide_dial(self) -> DialStorageService:
            return dial  # type: ignore[return-value]

    injector = Injector([TestModule()])
    return create_api_router(injector)


def _dial(bucket: str = "files/bucket") -> MagicMock:
    d = MagicMock()
    d.get_storage_home = AsyncMock(return_value=bucket)
    return d


# ---------------------------------------------------------------------------
# 401 — missing Api-Key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_api_key_returns_401() -> None:
    svc = MagicMock()
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.get("/memory")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_missing_api_key_on_delete_returns_401() -> None:
    svc = MagicMock()
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.delete("/memory/abc")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 200 — happy paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_returns_200() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(return_value=[_row()])
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.get("/memory", headers={"Api-Key": "k"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_by_id_returns_200() -> None:
    svc = MagicMock()
    svc.get_row = AsyncMock(return_value=_row("abc"))
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.get("/memory/abc", headers={"Api-Key": "k"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_returns_204() -> None:
    svc = MagicMock()
    svc.delete_row = AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.delete("/memory/abc", headers={"Api-Key": "k"})
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# 404 — not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_missing_row_returns_404() -> None:
    svc = MagicMock()
    svc.get_row = AsyncMock(side_effect=RowNotFoundError("not found"))
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.get("/memory/missing", headers={"Api-Key": "k"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 503 — StorageSyncError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_storage_sync_error_returns_503_with_message() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(side_effect=StorageSyncError("dial unreachable"))
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, _dial())), base_url="http://test"
    ) as c:
        r = await c.get("/memory", headers={"Api-Key": "k"})
    assert r.status_code == 503
    assert "message" in r.json()


