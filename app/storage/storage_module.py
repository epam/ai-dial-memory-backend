"""Injector bindings for LanceDB repository and storage sync."""

from __future__ import annotations

from injector import Binder, Module, singleton

from app.storage.repository import LanceDbMemoryRepository, MemoryRepository
from app.storage.sync import StorageSync


class StorageModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(MemoryRepository, to=LanceDbMemoryRepository, scope=singleton)
        binder.bind(StorageSync, to=StorageSync, scope=singleton)
