"""Tests for AppModule — DI composition root that wires all modules together."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from injector import Injector

from app.di.app_module import AppModule
from app.services.memory_service import MemoryService


def test_app_module_provides_memory_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    svc = injector.get(MemoryService)
    assert isinstance(svc, MemoryService)


def test_app_module_provides_fastapi_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    app = injector.get(FastAPI)
    assert isinstance(app, FastAPI)


def test_app_module_memory_service_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    svc1 = injector.get(MemoryService)
    svc2 = injector.get(MemoryService)
    assert svc1 is svc2
