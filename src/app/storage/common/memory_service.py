"""AbstractMemoryService — public interface for the memory backend."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.app.models.memory import MemoryRow, MemoryType, RetrieveResponse, StoreMemoryInput, StoreMemoryOutput


class AbstractMemoryService(ABC):
    @abstractmethod
    async def store(self, api_key: str, memory_input: StoreMemoryInput) -> StoreMemoryOutput: ...

    @abstractmethod
    async def search_archive(self, api_key: str, query: str, limit: int = 20) -> list[MemoryRow]: ...

    @abstractmethod
    async def retrieve(
        self,
        api_key: str,
        app_name: str | None,
        tier1_limit: int = 5,
        tier2_limit: int = 10,
    ) -> RetrieveResponse: ...

    @abstractmethod
    async def list_rows(
        self, api_key: str, memory_type: MemoryType | None = None
    ) -> list[MemoryRow]: ...

    @abstractmethod
    async def get_row(self, api_key: str, row_id: str) -> MemoryRow: ...

    @abstractmethod
    async def delete_row(self, api_key: str, row_id: str) -> None: ...
