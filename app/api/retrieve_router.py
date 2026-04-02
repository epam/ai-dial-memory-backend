"""REST router for memory retrieval: GET /memory/retrieve."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Query

from app.middleware.auth import UserContext
from app.models.memory import RetrieveResponse
from app.services.memory_service import MemoryService


def make_retrieve_router(
    service: MemoryService,
    user_context_dep: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/memory/retrieve", response_model=RetrieveResponse)
    async def retrieve_memory(
        query: str = Query(...),
        tier1_limit: int = Query(default=5),
        tier2_limit: int = Query(default=10),
        ctx: UserContext = Depends(user_context_dep),
    ) -> RetrieveResponse:
        return await service.retrieve(ctx.api_key, query, tier1_limit, tier2_limit)

    return router
