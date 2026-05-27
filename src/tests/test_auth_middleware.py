"""Unit tests for auth middleware — UserContext and get_user_context dependency."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.app.middleware.auth import UserContext, get_user_context


def _req(headers: dict) -> MagicMock:
    req = MagicMock()
    req.headers = headers
    return req


@pytest.mark.asyncio
async def test_raises_401_when_api_key_header_missing() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_user_context(_req({}))

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_returns_user_context_with_api_key() -> None:
    ctx = await get_user_context(_req({"Api-Key": "my-secret"}))

    assert isinstance(ctx, UserContext)
    assert ctx.api_key == "my-secret"
