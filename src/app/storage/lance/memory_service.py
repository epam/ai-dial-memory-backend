"""Concrete MemoryService — LanceDB backend implementation."""
from __future__ import annotations

import datetime
import uuid

from injector import inject

from src.app.models.memory import (
    MemoryRow,
    MemoryType,
    RetrieveResponse,
    StoreMemoryInput,
    StoreMemoryOutput,
)
from src.app.storage.common.errors import RowNotFoundError
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.common.repository import MemoryRepository
from src.app.storage.lance.sync import StorageSync


@inject
class MemoryService(AbstractMemoryService):
    def __init__(self, sync: StorageSync, repo: MemoryRepository) -> None:
        self._sync = sync
        self._repo = repo

    async def store(self, api_key: str, memory_input: StoreMemoryInput) -> StoreMemoryOutput:
        row = MemoryRow(
            id=str(uuid.uuid4()),
            memory_type=memory_input.memory_type,
            content=memory_input.content,
            context=memory_input.context,
            importance=memory_input.importance,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            access_count=0,
        )
        async with self._sync.open(api_key, write=True) as (_, bucket):
            self._repo.append(bucket, row)
        return StoreMemoryOutput(id=row.id, stored=True)

    async def search_archive(self, api_key: str, query: str, limit: int = 20) -> list[MemoryRow]:
        async with self._sync.open(api_key, write=False) as (_, bucket):
            return self._repo.fts_search(bucket, query, "episodic", limit)

    async def retrieve(
        self,
        api_key: str,
        query: str,
        tier1_limit: int = 5,
        tier2_limit: int = 10,
    ) -> RetrieveResponse:
        async with self._sync.open(api_key, write=False) as (_, bucket):
            tier1 = self._repo.top_by_importance(bucket, "core", tier1_limit)
            tier2 = self._repo.fts_search(bucket, query, "episodic", tier2_limit)

        seen: set[str] = set()
        facts: list[MemoryRow] = []
        for row in tier1:
            if row.id not in seen:
                seen.add(row.id)
                facts.append(row)
        for row in tier2:
            if row.id not in seen:
                seen.add(row.id)
                facts.append(row)
        return RetrieveResponse(facts=facts)

    async def list_rows(
        self, api_key: str, memory_type: MemoryType | None = None
    ) -> list[MemoryRow]:
        async with self._sync.open(api_key, write=False) as (_, bucket):
            return self._repo.list_rows(bucket, memory_type)

    async def get_row(self, api_key: str, row_id: str) -> MemoryRow:
        async with self._sync.open(api_key, write=False) as (_, bucket):
            row = self._repo.get(bucket, row_id)
        if row is None:
            raise RowNotFoundError(f"Row {row_id!r} not found")
        return row

    async def delete_row(self, api_key: str, row_id: str) -> None:
        async with self._sync.open(api_key, write=True) as (_, bucket):
            row = self._repo.get(bucket, row_id)
            if row is None:
                raise RowNotFoundError(f"Row {row_id!r} not found")
            self._repo.delete(bucket, row_id)
