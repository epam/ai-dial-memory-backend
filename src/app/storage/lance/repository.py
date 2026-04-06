from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import lancedb
import pyarrow as pa
from injector import inject

from src.app.config.app_settings import AppSettings
from src.app.models.memory import MemoryRow, MemoryType

logger = logging.getLogger(__name__)

MEMORY_SCHEMA = pa.schema([
    pa.field("id",              pa.string(),            nullable=False),
    pa.field("memory_type",     pa.string(),            nullable=False),
    pa.field("content",         pa.string(),            nullable=False),
    pa.field("context",         pa.string(),            nullable=False),
    pa.field("importance",      pa.float32(),           nullable=False),
    pa.field("embedding_model", pa.string(),            nullable=True),
    pa.field("vector",          pa.list_(pa.float32()), nullable=True),
    pa.field("timestamp",       pa.timestamp("us"),     nullable=False),
    pa.field("access_count",    pa.int32(),             nullable=False),
])


class MemoryRepository(ABC):
    @abstractmethod
    def append(self, bucket: str, row: MemoryRow) -> None: ...

    @abstractmethod
    def get(self, bucket: str, row_id: str) -> MemoryRow | None: ...

    @abstractmethod
    def list_rows(self, bucket: str, memory_type: MemoryType | None = None) -> list[MemoryRow]: ...

    @abstractmethod
    def delete(self, bucket: str, row_id: str) -> None: ...

    @abstractmethod
    def fts_search(self, bucket: str, query: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]: ...

    @abstractmethod
    def top_by_importance(self, bucket: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]: ...


@inject
class LanceDbMemoryRepository(MemoryRepository):
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def _table_path(self, bucket: str) -> Path:
        return self._settings.tmp_dir / bucket / "memory.lance"

    def _open_table(self, bucket: str) -> lancedb.table.LanceTable:
        db_path = self._table_path(bucket)
        db_path.mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(str(db_path.parent))
        table_name = "memory"
        if table_name not in db.table_names():
            table = db.create_table(table_name, schema=MEMORY_SCHEMA)
            table.create_fts_index("content", replace=True)
            return table
        table = db.open_table(table_name)
        return table

    def _row_to_model(self, record: dict) -> MemoryRow:
        return MemoryRow.model_validate(record)

    def append(self, bucket: str, row: MemoryRow) -> None:
        table = self._open_table(bucket)
        table.add([row.model_dump()])
        logger.debug("Appended row %s to bucket %s", row.id, bucket)

    def get(self, bucket: str, row_id: str) -> MemoryRow | None:
        table = self._open_table(bucket)
        results = (
            table.search()
                 .where(f"id = '{row_id}'", prefilter=True)
                 .limit(1)
                 .to_pandas()
        )
        if results.empty:
            return None
        return self._row_to_model(results.to_dict("records")[0])

    def list_rows(self, bucket: str, memory_type: MemoryType | None = None) -> list[MemoryRow]:
        table = self._open_table(bucket)
        q = table.search()
        if memory_type is not None:
            q = q.where(f"memory_type = '{memory_type}'", prefilter=True)
        records = q.limit(10_000).to_pandas().to_dict("records")
        return [self._row_to_model(r) for r in records]

    def delete(self, bucket: str, row_id: str) -> None:
        table = self._open_table(bucket)
        table.delete(f"id = '{row_id}'")
        logger.debug("Deleted row %s from bucket %s", row_id, bucket)

    def fts_search(self, bucket: str, query: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]:
        table = self._open_table(bucket)
        table.create_fts_index("content", replace=True)
        records = (
            table.search(query, query_type="fts")
                 .where(f"memory_type = '{memory_type}'", prefilter=True)
                 .limit(limit)
                 .to_pandas()
                 .to_dict("records")
        )
        return [self._row_to_model(r) for r in records]

    def top_by_importance(self, bucket: str, memory_type: MemoryType, limit: int) -> list[MemoryRow]:
        table = self._open_table(bucket)
        records = (
            table.search()
                 .where(f"memory_type = '{memory_type}'", prefilter=True)
                 .limit(limit)
                 .to_pandas()
                 .sort_values("importance", ascending=False)
                 .to_dict("records")
        )
        return [self._row_to_model(r) for r in records]
