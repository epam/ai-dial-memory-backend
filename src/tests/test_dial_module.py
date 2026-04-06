"""Injector wiring for DialModule."""

from __future__ import annotations

import pytest
from injector import Injector

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_module import DialModule
from src.app.dial.dial_storage import DialStorageService


def test_dial_module_resolves_dial_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.example")
    injector = Injector([DialModule()])
    svc = injector.get(DialStorageService)
    assert isinstance(svc, DialStorageService)
    settings = injector.get(AppSettings)
    assert settings.dial_url == "http://dial.example"
