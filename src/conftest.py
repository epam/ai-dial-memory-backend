"""
Root conftest.py — stubs lancedb for Windows development.

lancedb publishes no Windows wheel; all Windows tests that touch the
repository layer must use a mocked MemoryRepository instead of
LanceDbMemoryRepository.  The stub below lets the module be *imported*
without error so that the rest of the test suite can still load.

On Linux / CI the real lancedb wheel is available and this stub is
never invoked (the real package takes precedence).
"""
from __future__ import annotations

import sys
import types


def _stub_lancedb() -> None:
    """Insert a minimal lancedb stub into sys.modules if lancedb is absent."""
    try:
        import lancedb  # noqa: F401 — real package present, nothing to do
        return
    except ImportError:
        pass

    # Build a minimal stub that satisfies the import surface used in
    # app/storage/repository.py:  lancedb.connect(...)  and
    # lancedb.table.LanceTable (used only as a type annotation).
    lancedb_mod = types.ModuleType("lancedb")
    table_mod = types.ModuleType("lancedb.table")

    class _FakeLanceTable:
        """Placeholder so type annotations resolve at import time."""

    table_mod.LanceTable = _FakeLanceTable  # type: ignore[attr-defined]
    lancedb_mod.table = table_mod  # type: ignore[attr-defined]
    lancedb_mod.connect = lambda *a, **kw: (_ for _ in ()).throw(  # type: ignore[attr-defined]
        RuntimeError("lancedb is not installed — use a mocked MemoryRepository in tests")
    )

    sys.modules["lancedb"] = lancedb_mod
    sys.modules["lancedb.table"] = table_mod


_stub_lancedb()
