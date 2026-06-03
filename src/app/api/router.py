"""API router factory — builds a FastAPI app with routes, exception handler middleware,
and an Injector → FastAPI DI bridge."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from injector import Injector
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from src.app.api.configuration_support_router import make_configuration_support_router
from src.app.api.memory_router import make_memory_router
from src.app.config.application import MemoryAppConfig
from src.app.middleware.app_config import get_app_config
from src.app.middleware.auth import UserContext, get_user_context
from src.app.storage.common.errors import RowNotFoundError, StorageSyncError
from src.app.storage.common.memory_service import AbstractMemoryService


def create_api_router(injector: Injector, lifespan: Any = None) -> FastAPI:
    service = injector.get(AbstractMemoryService)  # type: ignore[type-abstract]

    async def _user_context_dep(request: Request) -> UserContext:
        return await get_user_context(request)

    async def _app_config_dep(request: Request) -> MemoryAppConfig:
        return await get_app_config(request)

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def _exception_handler(request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except StorageSyncError as exc:
            return JSONResponse(status_code=503, content={"message": str(exc)})
        except RowNotFoundError as exc:
            return JSONResponse(status_code=404, content={"message": str(exc)})
        except Exception:
            return JSONResponse(
                status_code=500, content={"message": "Internal server error"}
            )

    app.include_router(make_configuration_support_router())
    app.include_router(make_memory_router(service, _user_context_dep))
    return app
