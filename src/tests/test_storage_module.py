"""LanceModule injector bindings."""
from __future__ import annotations

import pytest
from injector import Injector

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_module import DialModule
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService
from src.app.storage.lance.module import LanceModule
from src.app.storage.common.repository import MemoryRepository
from src.app.storage.lance.repository import LanceDbMemoryRepository
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


def test_repository_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial")
    injector = Injector([DialModule(), LanceModule()])
    assert injector.get(MemoryRepository) is injector.get(MemoryRepository)
