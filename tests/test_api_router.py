"""Tests for create_api_router — Injector-FastAPI bridge and route mounting."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from injector import Injector, Module, provider, singleton

from app.api.router import create_api_router
from app.dial.dial_storage import DialStorageService
from app.middleware.auth import UserContext
from app.models.memory import MemoryRow, RetrieveResponse
from app.services.memory_service import MemoryService


def _row() -> MemoryRow:
    return MemoryRow(
        id="r1",
        memory_type="core",
        content="content",
        context="ctx",
        importance=0.9,
        timestamp=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        access_count=0,
    )


def _make_injector(svc: MagicMock, dial: MagicMock) -> Injector:
    class TestModule(Module):
        @provider
        @singleton
        def provide_service(self) -> MemoryService:
            return svc  # type: ignore[return-value]

        @provider
        @singleton
        def provide_dial(self) -> DialStorageService:
            return dial  # type: ignore[return-value]

    return Injector([TestModule()])


def _make_app(svc: MagicMock, dial: MagicMock) -> FastAPI:
    injector = _make_injector(svc, dial)
    return create_api_router(injector)


@pytest.mark.asyncio
async def test_list_memory_route_reachable_via_injector() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(return_value=[_row()])
    dial = MagicMock()
    dial.get_storage_home = AsyncMock(return_value="files/bucket")

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, dial)), base_url="http://test"
    ) as c:
        r = await c.get("/memory", headers={"Api-Key": "test-key"})

    assert r.status_code == 200


@pytest.mark.asyncio
async def test_retrieve_route_not_shadowed_by_memory_id_route() -> None:
    svc = MagicMock()
    svc.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[]))
    dial = MagicMock()
    dial.get_storage_home = AsyncMock(return_value="files/bucket")

    async with AsyncClient(
        transport=ASGITransport(app=_make_app(svc, dial)), base_url="http://test"
    ) as c:
        r = await c.get("/memory/retrieve?query=hello", headers={"Api-Key": "test-key"})

    assert r.status_code == 200
    svc.retrieve.assert_awaited_once()
