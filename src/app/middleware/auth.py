"""Authentication middleware — UserContext and get_user_context FastAPI dependency."""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import BaseModel


class UserContext(BaseModel):
    api_key: str


async def get_user_context(request: Request) -> UserContext:
    api_key: str | None = request.headers.get("Api-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Api-Key header missing")
    return UserContext(api_key=api_key)
