"""Authentication middleware — UserContext and get_user_context FastAPI dependency."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.dial.dial_storage import DialStorageService


@dataclass
class UserContext:
    api_key: str
    bucket: str


async def get_user_context(request: Request, dial: DialStorageService) -> UserContext:
    api_key: str | None = request.headers.get("Api-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="Api-Key header missing")
    bucket = await dial.get_storage_home(api_key)
    return UserContext(api_key=api_key, bucket=bucket)
