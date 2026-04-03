"""REST router for memory retrieval: GET /memory/retrieve."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Query

from app.config.application import MemoryAppConfig
from app.middleware.auth import UserContext
from app.models.memory import RetrieveResponse
from app.services.memory_service import MemoryService


def make_retrieve_router(
    service: MemoryService,
    user_context_dep: Callable,
    app_config_dep: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/memory/retrieve", response_model=RetrieveResponse)
    async def retrieve_memory(
        query: str = Query(...),
        ctx: UserContext = Depends(user_context_dep),
        app_config: MemoryAppConfig = Depends(app_config_dep),
    ) -> RetrieveResponse:
        return await service.retrieve(
            ctx.api_key, query, app_config.tier1_limit, app_config.tier2_limit
        )

    return router
