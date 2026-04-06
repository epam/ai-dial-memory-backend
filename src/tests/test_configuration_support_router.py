"""Tests for GET /v1/configuration-support/application-schema."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.api.configuration_support_router import make_configuration_support_router
from src.app.dial.dial_schema import DialJSONSchemaExtensions


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(make_configuration_support_router())
    return app


@pytest.mark.asyncio
async def test_schema_endpoint_returns_200() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as c:
        r = await c.get("/v1/configuration-support/application-schema")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_schema_endpoint_returns_json_object() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as c:
        r = await c.get("/v1/configuration-support/application-schema")
    assert isinstance(r.json(), dict)


@pytest.mark.asyncio
async def test_schema_endpoint_contains_tier_limit_properties() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as c:
        r = await c.get("/v1/configuration-support/application-schema")
    schema = r.json()
    assert "properties" in schema
    assert "tier1_limit" in schema["properties"]
    assert "tier2_limit" in schema["properties"]


@pytest.mark.asyncio
async def test_schema_endpoint_contains_dial_display_name() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as c:
        r = await c.get("/v1/configuration-support/application-schema")
    schema = r.json()
    assert DialJSONSchemaExtensions.APPLICATION_TYPE_DISPLAY_NAME in schema


@pytest.mark.asyncio
async def test_schema_endpoint_no_auth_required() -> None:
    """Schema endpoint is public — no Api-Key needed."""
    async with AsyncClient(
        transport=ASGITransport(app=_make_app()), base_url="http://test"
    ) as c:
        r = await c.get("/v1/configuration-support/application-schema")
    assert r.status_code == 200
