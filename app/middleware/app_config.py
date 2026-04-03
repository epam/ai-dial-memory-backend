"""App-config middleware — parse X-Dial-Application-Properties header into MemoryAppConfig."""
from __future__ import annotations

import json

from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.config.application import MemoryAppConfig

APP_PROPERTIES_HEADER = "X-Dial-Application-Properties"


async def get_app_config(request: Request) -> MemoryAppConfig:
    """FastAPI dependency that reads per-instance configuration from the DIAL header.

    Returns MemoryAppConfig defaults when the header is absent (e.g. direct API calls).
    Raises HTTP 422 for malformed JSON or schema validation failures.
    """
    header_value: str | None = request.headers.get(APP_PROPERTIES_HEADER)
    if not header_value:
        return MemoryAppConfig()
    try:
        data = json.loads(header_value)
        return MemoryAppConfig.model_validate(data)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON in {APP_PROPERTIES_HEADER}: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
