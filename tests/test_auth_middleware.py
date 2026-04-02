"""Unit tests for auth middleware — UserContext and get_user_context dependency."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.middleware.auth import UserContext, get_user_context


def _req(headers: dict) -> MagicMock:
    req = MagicMock()
    req.headers = headers
    return req


@pytest.mark.asyncio
async def test_raises_401_when_api_key_header_missing() -> None:
    dial = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_user_context(_req({}), dial)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_returns_user_context_with_api_key_and_bucket() -> None:
    dial = AsyncMock()
    dial.get_storage_home = AsyncMock(return_value="files/user/bucket")

    ctx = await get_user_context(_req({"Api-Key": "my-secret"}), dial)

    assert isinstance(ctx, UserContext)
    assert ctx.api_key == "my-secret"
    assert ctx.bucket == "files/user/bucket"
    dial.get_storage_home.assert_awaited_once_with("my-secret")
