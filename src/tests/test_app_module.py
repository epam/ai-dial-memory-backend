"""Tests for AppModule — DI composition root that wires all modules together."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from injector import Injector

from src.app.di.app_module import AppModule
from src.app.storage.common.memory_service import AbstractMemoryService


def test_app_module_provides_memory_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    svc = injector.get(AbstractMemoryService)
    assert isinstance(svc, AbstractMemoryService)


def test_app_module_provides_fastapi_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    app = injector.get(FastAPI)
    assert isinstance(app, FastAPI)


def test_app_module_memory_service_is_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    svc1 = injector.get(AbstractMemoryService)
    svc2 = injector.get(AbstractMemoryService)
    assert svc1 is svc2


def test_app_module_settings_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.app.config.app_settings import AppSettings

    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    injector = Injector([AppModule()])
    assert injector.get(AppSettings) is injector.get(AppSettings)
