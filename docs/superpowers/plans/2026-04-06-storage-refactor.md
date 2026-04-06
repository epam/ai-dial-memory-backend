# Storage Refactor: Common Abstractions + LanceDB Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `src/app/storage/` so database-agnostic contracts live in `storage/common/` and all LanceDB-specific code lives in `storage/lance/`, with `AbstractMemoryService` as the only public interface external callers depend on.

**Architecture:** `storage/common/` exposes `AbstractMemoryService` (ABC) and shared error types. `storage/lance/` is a self-contained backend: it contains `MemoryRepository` ABC + `LanceDbMemoryRepository`, `StorageSync`, concrete `MemoryService`, and `LanceModule` (DI bindings). Callers (API routers, MCP, DI root) depend only on `AbstractMemoryService` from `common/`. Closes beads tasks: `ai-dial-memory-mcp-0zr`, `ai-dial-memory-mcp-90j`, `ai-dial-memory-mcp-9mc`.

**Tech Stack:** Python 3.13, injector, FastAPI, LanceDB, pyarrow, pytest-asyncio

---

## File Map

### Created
- `src/app/storage/common/__init__.py` — empty
- `src/app/storage/common/errors.py` — `RowNotFoundError`, `StorageSyncError`
- `src/app/storage/common/memory_service.py` — `AbstractMemoryService` ABC
- `src/app/storage/lance/__init__.py` — empty
- `src/app/storage/lance/repository.py` — `MemoryRepository` ABC + `LanceDbMemoryRepository` + `MEMORY_SCHEMA`
- `src/app/storage/lance/sync.py` — `StorageSync`
- `src/app/storage/lance/memory_service.py` — concrete `MemoryService(AbstractMemoryService)`
- `src/app/storage/lance/module.py` — `LanceModule` DI bindings (scope fix included)

### Modified
- `src/app/di/app_module.py` — install `LanceModule`, use `AbstractMemoryService`
- `src/app/api/router.py` — use `AbstractMemoryService`, import errors from `common`
- `src/app/api/memory_router.py` — use `AbstractMemoryService`
- `src/app/api/retrieve_router.py` — use `AbstractMemoryService`
- `src/app/mcp/tools.py` — use `AbstractMemoryService`
- `src/tests/test_memory_service.py` — update imports, add isinstance check
- `src/tests/test_storage_module.py` — replace `StorageModule` with `LanceModule`, update imports
- `src/tests/test_memory_repository.py` — update import path + patch path
- `src/tests/test_storage_sync.py` — update import
- `src/tests/test_storage_sync_logging.py` — update import + logger name
- `src/tests/test_mcp_tools_integration.py` — update imports
- `src/tests/test_exception_handler.py` — update imports
- `src/tests/test_memory_router.py` — update imports
- `src/tests/test_rest_integration.py` — update imports
- `src/tests/test_api_router.py` — update imports
- `src/tests/test_app_module.py` — update imports

### Deleted
- `src/app/storage/repository.py`
- `src/app/storage/sync.py`
- `src/app/storage/storage_module.py`
- `src/app/services/memory_service.py`
- `src/app/services/__init__.py`

---

## Task 1: Create `storage/common/errors.py`

**Files:**
- Create: `src/app/storage/common/__init__.py`
- Create: `src/app/storage/common/errors.py`

- [ ] **Step 1: Create the files**

`src/app/storage/common/__init__.py` — empty file.

`src/app/storage/common/errors.py`:
```python
"""Shared error types for the storage module public interface."""
from __future__ import annotations


class RowNotFoundError(Exception):
    """Raised when a requested memory row does not exist."""


class StorageSyncError(Exception):
    """Raised when pulling or pushing the remote dataset fails."""
```

- [ ] **Step 2: Verify importable**

```bash
python -c "from src.app.storage.common.errors import RowNotFoundError, StorageSyncError; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/app/storage/common/
git commit -m "feat(storage): add common/errors.py with RowNotFoundError and StorageSyncError"
```

---

## Task 2: Create `AbstractMemoryService` in `storage/common/memory_service.py`

**Files:**
- Create: `src/app/storage/common/memory_service.py`

- [ ] **Step 1: Write failing test**

Add to `src/tests/test_memory_service.py` (at the top of the file, alongside existing imports — do NOT run yet):

The test will import from the new path. Since the file doesn't exist yet, the import will fail — that's the "red" state.

```python
# Add this import at top:
from src.app.storage.common.memory_service import AbstractMemoryService

# Add this test:
def test_abstract_memory_service_is_abstract() -> None:
    import inspect
    assert inspect.isabstract(AbstractMemoryService)
    abstract_methods = {
        "store", "search_archive", "retrieve", "list_rows", "get_row", "delete_row"
    }
    assert AbstractMemoryService.__abstractmethods__ == abstract_methods
```

- [ ] **Step 2: Run to confirm it fails**

```bash
python -m pytest src/tests/test_memory_service.py::test_abstract_memory_service_is_abstract -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.app.storage.common.memory_service'`

- [ ] **Step 3: Create the ABC**

`src/app/storage/common/memory_service.py`:
```python
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
        query: str,
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest src/tests/test_memory_service.py::test_abstract_memory_service_is_abstract -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/app/storage/common/memory_service.py src/tests/test_memory_service.py
git commit -m "feat(storage): add AbstractMemoryService ABC in storage/common"
```

---

## Task 3: Create `storage/lance/repository.py`

Move `MemoryRepository` ABC and `LanceDbMemoryRepository` from `storage/repository.py` into the lance subpackage.

**Files:**
- Create: `src/app/storage/lance/__init__.py`
- Create: `src/app/storage/lance/repository.py`

- [ ] **Step 1: Create the files**

`src/app/storage/lance/__init__.py` — empty file.

`src/app/storage/lance/repository.py` — copy the entire content of `src/app/storage/repository.py` and update the one internal import:

```python
"""LanceDB implementation of MemoryRepository."""
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
```

- [ ] **Step 2: Update `test_memory_repository.py` imports and patch path**

In `src/tests/test_memory_repository.py`, change:
```python
# OLD:
from src.app.storage.repository import LanceDbMemoryRepository

# NEW:
from src.app.storage.lance.repository import LanceDbMemoryRepository
```

Also change all six `patch("src.app.storage.repository.lancedb.connect", ...)` calls to:
```python
patch("src.app.storage.lance.repository.lancedb.connect", ...)
```

- [ ] **Step 3: Run repository tests**

```bash
python -m pytest src/tests/test_memory_repository.py -v
```
Expected: `6 passed`

- [ ] **Step 4: Update `test_mcp_tools_integration.py`**

Change:
```python
# OLD:
from src.app.storage.repository import MemoryRepository

# NEW:
from src.app.storage.lance.repository import MemoryRepository
```

- [ ] **Step 5: Commit**

```bash
git add src/app/storage/lance/ src/tests/test_memory_repository.py src/tests/test_mcp_tools_integration.py
git commit -m "feat(storage): add lance/repository.py, update tests to new import path"
```

---

## Task 4: Create `storage/lance/sync.py`

Move `StorageSync` from `storage/sync.py`. `StorageSyncError` moves to `common/errors.py` (already done in Task 1) — `sync.py` imports it from there.

**Files:**
- Create: `src/app/storage/lance/sync.py`

- [ ] **Step 1: Create the file**

`src/app/storage/lance/sync.py`:
```python
"""Sync-down / sync-up gateway between DIAL BLOB and local LanceDB paths."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from injector import inject

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_storage import DialStorageError, DialStorageService
from src.app.storage.common.errors import StorageSyncError

logger = logging.getLogger(__name__)


def _bucket_id(storage_home: str) -> str:
    """Stable filesystem-safe id for this user's storage root."""
    return hashlib.sha256(storage_home.encode("utf-8")).hexdigest()


@inject
class StorageSync:
    def __init__(
        self,
        dial: DialStorageService,
        settings: AppSettings,
    ) -> None:
        self._dial = dial
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, bucket_id: str) -> asyncio.Lock:
        if bucket_id not in self._locks:
            self._locks[bucket_id] = asyncio.Lock()
        return self._locks[bucket_id]

    def _remote_memory_prefix(self, storage_home: str) -> str:
        return f"{storage_home.rstrip('/')}/memory/memory.lance"

    async def _sync_down(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        """Best-effort pull of remote `memory.lance` tree into ``local_lance``."""
        remote = self._remote_memory_prefix(storage_home)
        local_lance.parent.mkdir(parents=True, exist_ok=True)
        if local_lance.exists():
            shutil.rmtree(local_lance)
        try:
            await self._dial.download(api_key, remote, local_lance)
        except DialStorageError as exc:
            if _is_not_found(exc):
                logger.info("No remote memory dataset at %s; starting fresh", remote)
                local_lance.mkdir(parents=True, exist_ok=True)
            else:
                raise StorageSyncError(f"sync-down failed: {exc}") from exc

    async def _sync_up(
        self,
        api_key: str,
        storage_home: str,
        local_lance: Path,
    ) -> None:
        remote = self._remote_memory_prefix(storage_home)
        try:
            await self._dial.upload(api_key, local_lance, remote)
        except DialStorageError as exc:
            raise StorageSyncError(f"sync-up failed: {exc}") from exc

    @asynccontextmanager
    async def open(
        self,
        api_key: str,
        *,
        write: bool,
    ) -> AsyncGenerator[tuple[Path, str]]:
        """Sync down, yield ``(path_to_memory_lance, bucket_id)``, sync up on write."""
        storage_home = await self._dial.get_storage_home(api_key)
        bucket_id = _bucket_id(storage_home)
        lock = self._lock_for(bucket_id)
        _log = {"bucket": bucket_id}
        async with lock:
            local_lance = self._settings.tmp_dir / bucket_id / "memory.lance"
            logger.debug("sync-down start", extra=_log)
            try:
                await self._sync_down(api_key, storage_home, local_lance)
            except StorageSyncError:
                raise
            logger.debug("sync-down end", extra=_log)
            try:
                yield local_lance, bucket_id
            finally:
                if write:
                    logger.debug("sync-up start", extra=_log)
                    await self._sync_up(api_key, storage_home, local_lance)
                    logger.debug("sync-up end", extra=_log)


def _is_not_found(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "404" in text or "not found" in text
```

- [ ] **Step 2: Update `test_storage_sync.py`**

Change:
```python
# OLD:
from src.app.storage.sync import StorageSync

# NEW:
from src.app.storage.lance.sync import StorageSync
```

- [ ] **Step 3: Update `test_storage_sync_logging.py`**

Change imports and logger name:
```python
# OLD:
from src.app.storage.sync import StorageSync
...
logger = logging.getLogger("src.app.storage.sync")

# NEW:
from src.app.storage.lance.sync import StorageSync
...
logger = logging.getLogger("src.app.storage.lance.sync")
```

- [ ] **Step 4: Run sync tests**

```bash
python -m pytest src/tests/test_storage_sync.py src/tests/test_storage_sync_logging.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/app/storage/lance/sync.py src/tests/test_storage_sync.py src/tests/test_storage_sync_logging.py
git commit -m "feat(storage): add lance/sync.py, StorageSyncError imported from common/errors"
```

---

## Task 5: Create `storage/lance/memory_service.py`

Move the concrete `MemoryService` from `services/memory_service.py` to `lance/memory_service.py`. Make it extend `AbstractMemoryService`.

**Files:**
- Create: `src/app/storage/lance/memory_service.py`

- [ ] **Step 1: Create the file**

`src/app/storage/lance/memory_service.py`:
```python
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
from src.app.storage.lance.repository import MemoryRepository
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
```

- [ ] **Step 2: Update `test_memory_service.py`**

Replace all imports at the top:
```python
# OLD:
from src.app.services.memory_service import MemoryService, RowNotFoundError

# NEW:
from src.app.storage.common.errors import RowNotFoundError
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService
```

Add one new test at the bottom of the file:
```python
def test_memory_service_implements_abstract_interface() -> None:
    assert issubclass(MemoryService, AbstractMemoryService)
```

- [ ] **Step 3: Update `test_mcp_tools_integration.py`**

Change:
```python
# OLD:
from src.app.services.memory_service import MemoryService

# NEW:
from src.app.storage.lance.memory_service import MemoryService
```

- [ ] **Step 4: Run memory service tests**

```bash
python -m pytest src/tests/test_memory_service.py src/tests/test_mcp_tools_integration.py -v
```
Expected: all pass (10 + 2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/app/storage/lance/memory_service.py src/tests/test_memory_service.py src/tests/test_mcp_tools_integration.py
git commit -m "feat(storage): add lance/memory_service.py extending AbstractMemoryService"
```

---

## Task 6: Create `storage/lance/module.py` with corrected DI scope

This replaces `storage/storage_module.py` and the `MemoryService` binding in `app_module.py`.

**Scope decisions (resolves ai-dial-memory-mcp-9mc):**
- `LanceDbMemoryRepository` → `noscope` (transient): holds only `AppSettings`, opens fresh DB connection per call — no shared state, singleton provides no benefit
- `StorageSync` → `singleton`: MUST be singleton to share `_locks: dict[str, asyncio.Lock]` across all requests — without this, concurrent requests to the same bucket would have independent locks and corrupt data
- `MemoryService` → `singleton`: stateless orchestrator; singleton is correct

**Files:**
- Create: `src/app/storage/lance/module.py`

- [ ] **Step 1: Write failing test**

In `src/tests/test_storage_module.py`, replace the entire file:
```python
"""LanceModule injector bindings."""
from __future__ import annotations

import pytest
from injector import Injector, noscope

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_module import DialModule
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService
from src.app.storage.lance.module import LanceModule
from src.app.storage.lance.repository import LanceDbMemoryRepository, MemoryRepository
from src.app.storage.lance.sync import StorageSync


def test_lance_module_resolves_repository_and_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), LanceModule()])
    repo = injector.get(MemoryRepository)
    sync = injector.get(StorageSync)
    assert isinstance(repo, LanceDbMemoryRepository)
    assert isinstance(sync, StorageSync)
    assert injector.get(AppSettings).dial_url == "http://dial"


def test_lance_module_resolves_abstract_memory_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), LanceModule()])
    svc = injector.get(AbstractMemoryService)
    assert isinstance(svc, MemoryService)


def test_storage_sync_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), LanceModule()])
    assert injector.get(StorageSync) is injector.get(StorageSync)


def test_repository_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), LanceModule()])
    assert injector.get(MemoryRepository) is not injector.get(MemoryRepository)
```

- [ ] **Step 2: Run to confirm tests fail**

```bash
python -m pytest src/tests/test_storage_module.py -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.app.storage.lance.module'`

- [ ] **Step 3: Create the module**

`src/app/storage/lance/module.py`:
```python
"""LanceModule — DI bindings for the LanceDB storage backend."""
from __future__ import annotations

from injector import Binder, Module, noscope, singleton

from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService
from src.app.storage.lance.repository import LanceDbMemoryRepository, MemoryRepository
from src.app.storage.lance.sync import StorageSync


class LanceModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(MemoryRepository, to=LanceDbMemoryRepository, scope=noscope)
        binder.bind(StorageSync, to=StorageSync, scope=singleton)
        binder.bind(AbstractMemoryService, to=MemoryService, scope=singleton)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest src/tests/test_storage_module.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/app/storage/lance/module.py src/tests/test_storage_module.py
git commit -m "feat(storage): add lance/module.py with LanceModule; fix DI scope (noscope repo, singleton sync)"
```

---

## Task 7: Update all callers to use new import paths

**Files:**
- Modify: `src/app/di/app_module.py`
- Modify: `src/app/api/router.py`
- Modify: `src/app/api/memory_router.py`
- Modify: `src/app/api/retrieve_router.py`
- Modify: `src/app/mcp/tools.py`
- Modify: `src/tests/test_exception_handler.py`
- Modify: `src/tests/test_memory_router.py`
- Modify: `src/tests/test_rest_integration.py`
- Modify: `src/tests/test_api_router.py`
- Modify: `src/tests/test_app_module.py`

- [ ] **Step 1: Update `src/app/di/app_module.py`**

```python
"""AppModule — root DI composition: wires DialModule, LanceModule, FastAPI."""
from __future__ import annotations

from fastapi import FastAPI
from injector import Binder, Injector, Module, provider, singleton

from src.app.api.router import create_api_router
from src.app.dial.dial_module import DialModule
from src.app.mcp.tools import create_mcp_server
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.module import LanceModule


class AppModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.install(DialModule())
        binder.install(LanceModule())

    @provider
    @singleton
    def provide_app(self, service: AbstractMemoryService, injector: Injector) -> FastAPI:
        mcp_server = create_mcp_server(service)
        api_app = create_api_router(injector)
        api_app.mount("/mcp", mcp_server.streamable_http_app())
        return api_app
```

- [ ] **Step 2: Update `src/app/api/router.py`**

```python
"""API router factory."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from injector import Injector

from src.app.api.configuration_support_router import make_configuration_support_router
from src.app.api.memory_router import make_memory_router
from src.app.api.retrieve_router import make_retrieve_router
from src.app.config.application import MemoryAppConfig
from src.app.dial.dial_storage import DialStorageService
from src.app.middleware.app_config import get_app_config
from src.app.middleware.auth import UserContext, get_user_context
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
from src.app.storage.common.memory_service import AbstractMemoryService


def create_api_router(injector: Injector) -> FastAPI:
    service = injector.get(AbstractMemoryService)
    dial = injector.get(DialStorageService)

    async def _user_context_dep(request: Request) -> UserContext:
        return await get_user_context(request, dial)

    async def _app_config_dep(request: Request) -> MemoryAppConfig:
        return await get_app_config(request)

    app = FastAPI()

    @app.middleware("http")
    async def _exception_handler(request: Request, call_next):  # noqa: ANN001
        try:
            return await call_next(request)
        except StorageSyncError as exc:
            return JSONResponse(status_code=503, content={"message": str(exc)})
        except RowNotFoundError as exc:
            return JSONResponse(status_code=404, content={"message": str(exc)})
        except Exception:
            return JSONResponse(status_code=500, content={"message": "Internal server error"})

    app.include_router(make_configuration_support_router())
    app.include_router(make_retrieve_router(service, _user_context_dep, _app_config_dep))
    app.include_router(make_memory_router(service, _user_context_dep))
    return app
```

- [ ] **Step 3: Update `src/app/api/memory_router.py`**

Change the import and type hint:
```python
# OLD:
from src.app.services.memory_service import MemoryService
def make_memory_router(service: MemoryService, ...) -> APIRouter:

# NEW:
from src.app.storage.common.memory_service import AbstractMemoryService
def make_memory_router(service: AbstractMemoryService, ...) -> APIRouter:
```

- [ ] **Step 4: Update `src/app/api/retrieve_router.py`**

```python
# OLD:
from src.app.services.memory_service import MemoryService
def make_retrieve_router(service: MemoryService, ...) -> APIRouter:

# NEW:
from src.app.storage.common.memory_service import AbstractMemoryService
def make_retrieve_router(service: AbstractMemoryService, ...) -> APIRouter:
```

- [ ] **Step 5: Update `src/app/mcp/tools.py`**

```python
# OLD:
from src.app.services.memory_service import MemoryService
def create_mcp_server(service: MemoryService) -> FastMCP:

# NEW:
from src.app.storage.common.memory_service import AbstractMemoryService
def create_mcp_server(service: AbstractMemoryService) -> FastMCP:
```

- [ ] **Step 6: Update test imports**

`src/tests/test_exception_handler.py`:
```python
# OLD:
from src.app.services.memory_service import MemoryService, RowNotFoundError
from src.app.storage.sync import StorageSyncError

# NEW:
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
from src.app.storage.common.memory_service import AbstractMemoryService
# Replace any direct MemoryService usage with AbstractMemoryService or MagicMock
```

`src/tests/test_memory_router.py`:
```python
# OLD:
from src.app.services.memory_service import RowNotFoundError
from src.app.storage.sync import StorageSyncError

# NEW:
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
```

`src/tests/test_rest_integration.py`:
```python
# OLD:
from src.app.services.memory_service import MemoryService, RowNotFoundError
from src.app.storage.sync import StorageSyncError

# NEW:
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
from src.app.storage.common.memory_service import AbstractMemoryService
# Replace MemoryService type hints with AbstractMemoryService
```

`src/tests/test_api_router.py`:
```python
# OLD:
from src.app.services.memory_service import MemoryService

# NEW:
from src.app.storage.common.memory_service import AbstractMemoryService
# Replace MemoryService with AbstractMemoryService in test body
```

`src/tests/test_app_module.py`:
```python
# OLD:
from src.app.services.memory_service import MemoryService

# NEW:
from src.app.storage.common.memory_service import AbstractMemoryService
# Replace MemoryService with AbstractMemoryService in test body
```

- [ ] **Step 7: Run full test suite (old files still present — expect passes)**

```bash
python -m pytest src/tests/ -v 2>&1 | tail -20
```
Expected: all tests that were passing before still pass. (Old files still exist, new files also work.)

- [ ] **Step 8: Commit**

```bash
git add src/app/di/app_module.py src/app/api/ src/app/mcp/tools.py src/tests/
git commit -m "refactor(storage): update all callers to use AbstractMemoryService and new import paths"
```

---

## Task 8: Delete old files and verify

**Files:**
- Delete: `src/app/storage/repository.py`
- Delete: `src/app/storage/sync.py`
- Delete: `src/app/storage/storage_module.py`
- Delete: `src/app/services/memory_service.py`
- Delete: `src/app/services/__init__.py`

- [ ] **Step 1: Delete the old source files**

```bash
rm src/app/storage/repository.py
rm src/app/storage/sync.py
rm src/app/storage/storage_module.py
rm src/app/services/memory_service.py
rm src/app/services/__init__.py
rmdir src/app/services/
```

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest src/tests/ -v 2>&1 | tail -30
```
Expected: all 126+ tests pass, no import errors.

- [ ] **Step 3: Verify no stale imports remain**

```bash
grep -rn "from src.app.storage.repository\|from src.app.storage.sync\|from src.app.storage.storage_module\|from src.app.services.memory_service" src/ --include="*.py" | grep -v __pycache__
```
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(storage): delete old repository.py, sync.py, storage_module.py, services/memory_service.py"
```

---

## Task 9: Close beads tasks

- [ ] **Step 1: Update task descriptions with Done notes and close**

```bash
bd close ai-dial-memory-mcp-0zr --reason="storage/common + storage/lance created; all callers updated; old files deleted"
bd close ai-dial-memory-mcp-90j --reason="AbstractMemoryService ABC added in common/memory_service.py; concrete MemoryService in lance/memory_service.py"
bd close ai-dial-memory-mcp-9mc --reason="LanceDbMemoryRepository scope=noscope (stateless); StorageSync scope=singleton (shared locks)"
```

- [ ] **Step 2: Push**

```bash
git pull --rebase
bd dolt push
git push
```
