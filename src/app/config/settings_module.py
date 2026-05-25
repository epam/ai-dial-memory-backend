from __future__ import annotations

from injector import Binder, Module, singleton

from src.app.config.app_settings import AppSettings


class SettingsModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(AppSettings, to=AppSettings, scope=singleton)
