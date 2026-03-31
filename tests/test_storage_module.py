"""StorageModule injector bindings."""

from __future__ import annotations

import pytest
from injector import Injector

from app.config.app_settings import AppSettings
from app.dial.dial_module import DialModule
from app.storage.repository import LanceDbMemoryRepository, MemoryRepository
from app.storage.storage_module import StorageModule
from app.storage.sync import StorageSync


def test_storage_module_resolves_repository_and_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), StorageModule()])
    repo = injector.get(MemoryRepository)
    sync = injector.get(StorageSync)
    assert isinstance(repo, LanceDbMemoryRepository)
    assert isinstance(sync, StorageSync)
    assert injector.get(AppSettings).dial_url == "http://dial"
