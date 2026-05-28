"""LanceModule — DI bindings for the LanceDB storage backend."""
from __future__ import annotations

from injector import Binder, Module, singleton

from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.memory_service import MemoryService
from src.app.storage.common.repository import MemoryRepository
from src.app.storage.lance.repository import LanceDbMemoryRepository
from src.app.storage.lance.sync import StorageSync


class LanceModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(MemoryRepository, to=LanceDbMemoryRepository, scope=singleton)
        binder.bind(StorageSync, to=StorageSync, scope=singleton)
        binder.bind(AbstractMemoryService, to=MemoryService, scope=singleton)
