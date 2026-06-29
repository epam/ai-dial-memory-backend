"""AppModule — root DI composition: wires DialModule, LanceModule, FastAPI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aidial_sdk import DIALApp
from fastapi import FastAPI
from injector import Binder, Injector, Module, provider, singleton

from src.app.api.router import create_api_router
from src.app.config.settings_module import SettingsModule
from src.app.middleware.logging import add_logging_middleware
from src.app.dial.completion import MemoryCompletion
from src.app.dial.dial_module import DialModule
from src.app.dial.dial_storage import DialStorageService
from src.app.mcp.tools import create_mcp_server
from src.app.storage.common.memory_service import AbstractMemoryService
from src.app.storage.lance.module import LanceModule


class AppModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.install(SettingsModule())
        binder.install(DialModule())
        binder.install(LanceModule())

    @provider
    @singleton
    def provide_app(
        self,
        service: AbstractMemoryService,
        dial_storage: DialStorageService,
        injector: Injector,
    ) -> FastAPI:
        mcp_server = create_mcp_server(service)
        mcp_sub_app = (
            mcp_server.streamable_http_app()
        )  # lazily initializes session_manager

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            async with mcp_server.session_manager.run():
                yield

        dial_app = DIALApp(lifespan=lifespan)
        dial_app.add_chat_completion("memory", MemoryCompletion(dial_storage))

        create_api_router(injector, app=dial_app)
        add_logging_middleware(dial_app)
        dial_app.mount("/mcp", mcp_sub_app)
        return dial_app
