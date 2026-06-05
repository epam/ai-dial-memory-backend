"""Unit tests for get_app_config dependency."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.app.config.application import MemoryAppConfig
from src.app.middleware.app_config import get_app_config


def _req(headers: dict[str, str]) -> MagicMock:
    req = MagicMock()
    req.headers = headers
    return req


@pytest.mark.asyncio
async def test_returns_defaults_when_header_absent() -> None:
    cfg = await get_app_config(_req({}))
    assert isinstance(cfg, MemoryAppConfig)
    assert cfg.tier1_limit == 5
    assert cfg.tier2_limit == 10


@pytest.mark.asyncio
async def test_parses_valid_app_properties() -> None:
    props = json.dumps({"tier1_limit": 3, "tier2_limit": 7})
    cfg = await get_app_config(_req({"X-Dial-Application-Properties": props}))
    assert cfg.tier1_limit == 3
    assert cfg.tier2_limit == 7


@pytest.mark.asyncio
async def test_partial_properties_merges_with_defaults() -> None:
    props = json.dumps({"tier1_limit": 2})
    cfg = await get_app_config(_req({"X-Dial-Application-Properties": props}))
    assert cfg.tier1_limit == 2
    assert cfg.tier2_limit == 10  # default kept


@pytest.mark.asyncio
async def test_raises_422_for_invalid_json() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_app_config(_req({"X-Dial-Application-Properties": "not-valid-json"}))
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_raises_422_for_wrong_types() -> None:
    props = json.dumps({"tier1_limit": "not-an-integer"})
    with pytest.raises(HTTPException) as exc_info:
        await get_app_config(_req({"X-Dial-Application-Properties": props}))
    assert exc_info.value.status_code == 422
