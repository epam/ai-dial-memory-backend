"""REST router for memory CRUD: GET /memory, GET /memory/{id}, DELETE /memory/{id}."""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from src.app.middleware.auth import UserContext
from src.app.models.memory import MemoryRow, MemoryType
from src.app.storage.common.memory_service import AbstractMemoryService


def make_memory_router(
    service: AbstractMemoryService,
    user_context_dep: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/memory", response_model=list[MemoryRow])
    async def list_memory(
        memory_type: MemoryType | None = Query(default=None),
        ctx: UserContext = Depends(user_context_dep),
    ) -> list[MemoryRow]:
        return await service.list_rows(ctx.api_key, memory_type)

    @router.get("/memory/{row_id}", response_model=MemoryRow)
    async def get_memory(
        row_id: str,
        ctx: UserContext = Depends(user_context_dep),
    ) -> MemoryRow:
        return await service.get_row(ctx.api_key, row_id)

    @router.delete("/memory/{row_id}", status_code=204)
    async def delete_memory(
        row_id: str,
        ctx: UserContext = Depends(user_context_dep),
    ) -> Response:
        await service.delete_row(ctx.api_key, row_id)
        return Response(status_code=204)

    return router
