"""Integration tests for memory_router and retrieve_router REST endpoints."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from src.app.config.application import MemoryAppConfig
from src.app.models.memory import MemoryRow, RetrieveResponse
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError


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


def _make_app(svc: MagicMock) -> FastAPI:
    """Build a minimal FastAPI app with real routers and a mocked MemoryService."""
    from src.app.api.memory_router import make_memory_router
    from src.app.api.retrieve_router import make_retrieve_router
    from src.app.middleware.app_config import get_app_config
    from src.app.middleware.auth import UserContext

    app = FastAPI()

    @app.middleware("http")
    async def _exc(request: Request, call_next):  # noqa: ANN001
        try:
            return await call_next(request)
        except RowNotFoundError as exc:
            return JSONResponse(status_code=404, content={"message": str(exc)})
        except StorageSyncError as exc:
            return JSONResponse(status_code=503, content={"message": str(exc)})

    async def _fake_user_context() -> UserContext:
        return UserContext(api_key="test-key", bucket="test-bucket")

    async def _app_config_dep(request: Request) -> MemoryAppConfig:
        return await get_app_config(request)

    memory_router = make_memory_router(svc, _fake_user_context)
    retrieve_router = make_retrieve_router(svc, _fake_user_context, _app_config_dep)

    # retrieve_router first: /memory/retrieve must not be shadowed by /memory/{row_id}
    app.include_router(retrieve_router)
    app.include_router(memory_router)
    return app


# ---------------------------------------------------------------------------
# memory_router: GET /memory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_memory_returns_200_with_rows() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(return_value=[_row()])
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.get("/memory", headers={"Api-Key": "k"})
    assert r.status_code == 200
    assert r.json()[0]["id"] == "r1"


@pytest.mark.asyncio
async def test_list_memory_passes_memory_type_filter() -> None:
    svc = MagicMock()
    svc.list_rows = AsyncMock(return_value=[])
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        await c.get("/memory?memory_type=core", headers={"Api-Key": "k"})
    svc.list_rows.assert_awaited_once_with("test-key", "core")


# ---------------------------------------------------------------------------
# memory_router: GET /memory/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_memory_by_id_returns_200() -> None:
    svc = MagicMock()
    svc.get_row = AsyncMock(return_value=_row("abc"))
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.get("/memory/abc", headers={"Api-Key": "k"})
    assert r.status_code == 200
    assert r.json()["id"] == "abc"


@pytest.mark.asyncio
async def test_get_memory_by_id_returns_404_when_not_found() -> None:
    svc = MagicMock()
    svc.get_row = AsyncMock(side_effect=RowNotFoundError("not found"))
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.get("/memory/missing", headers={"Api-Key": "k"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# memory_router: DELETE /memory/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_memory_returns_204() -> None:
    svc = MagicMock()
    svc.delete_row = AsyncMock()
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.delete("/memory/abc", headers={"Api-Key": "k"})
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_memory_returns_404_when_not_found() -> None:
    svc = MagicMock()
    svc.delete_row = AsyncMock(side_effect=RowNotFoundError("not found"))
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.delete("/memory/missing", headers={"Api-Key": "k"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# retrieve_router: GET /memory/retrieve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_returns_200_with_facts() -> None:
    svc = MagicMock()
    svc.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[_row()]))
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        r = await c.get("/memory/retrieve?query=hello", headers={"Api-Key": "k"})
    assert r.status_code == 200
    assert r.json()["facts"][0]["id"] == "r1"


@pytest.mark.asyncio
async def test_retrieve_passes_tier_limits_from_app_properties() -> None:
    import json

    svc = MagicMock()
    svc.retrieve = AsyncMock(return_value=RetrieveResponse(facts=[]))
    props = json.dumps({"tier1_limit": 3, "tier2_limit": 7})
    async with AsyncClient(transport=ASGITransport(app=_make_app(svc)), base_url="http://test") as c:
        await c.get(
            "/memory/retrieve?query=hi",
            headers={"Api-Key": "k", "X-Dial-Application-Properties": props},
        )
    svc.retrieve.assert_awaited_once_with("test-key", "hi", 3, 7)
