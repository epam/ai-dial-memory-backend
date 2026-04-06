"""AppModule — root DI composition: wires DialModule, LanceModule, FastAPI."""
from __future__ import annotations

from fastapi import FastAPI
from injector import Binder, Injector, Module, provider, singleton

from src.app.api.router import create_api_router
from src.app.dial.dial_module import DialModule
from src.app.mcp.tools import create_mcp_server
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.module import LanceModule


class AppModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.install(DialModule())
        binder.install(LanceModule())

    @provider
    @singleton
    def provide_app(self, service: AbstractMemoryService, injector: Injector) -> FastAPI:
        mcp_server = create_mcp_server(service)
        api_app = create_api_router(injector)
        api_app.mount("/mcp", mcp_server.streamable_http_app())
        return api_app
