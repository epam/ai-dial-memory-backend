"""MemoryRepository — public abstract interface for memory storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.app.models.memory import MemoryRow, MemoryType


class MemoryRepository(ABC):
    @abstractmethod
    def append(self, bucket: str, row: MemoryRow) -> None: ...

    @abstractmethod
    def get(self, bucket: str, row_id: str) -> MemoryRow | None: ...

    @abstractmethod
    def list_rows(
        self, bucket: str, memory_type: MemoryType | None = None
    ) -> list[MemoryRow]: ...

    @abstractmethod
    def delete(self, bucket: str, row_id: str) -> None: ...

    @abstractmethod
    def fts_search(
        self, bucket: str, query: str, memory_type: MemoryType, limit: int
    ) -> list[MemoryRow]: ...

    @abstractmethod
    def top_by_importance(
        self, bucket: str, memory_type: MemoryType, limit: int
    ) -> list[MemoryRow]: ...

    @abstractmethod
    def filter_by_context(
        self, bucket: str, context: str, memory_type: MemoryType, limit: int
    ) -> list[MemoryRow]: ...
