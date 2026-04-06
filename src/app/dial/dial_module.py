"""Injector module wiring for DIAL file storage."""

from __future__ import annotations

from injector import Binder, Module, singleton

from src.app.config.app_settings import AppSettings
from src.app.dial.dial_storage import DialStorageService


class DialModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(AppSettings, to=AppSettings, scope=singleton)
        binder.bind(DialStorageService, to=DialStorageService, scope=singleton)
