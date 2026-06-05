"""Configuration-support router — exposes live JSON schema for DIAL Core."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.app.config.application import MemoryAppConfig


def make_configuration_support_router() -> APIRouter:
    router = APIRouter(prefix="/v1/configuration-support")

    @router.get("/application-schema")
    async def get_application_schema() -> JSONResponse:
        """Return the live MemoryAppConfig JSON schema.

        DIAL Core can be pointed at this endpoint via
        ``dial:applicationTypeSchemaEndpoint`` so it always has the current schema
        without requiring manual schema file updates after each deployment.
        """
        schema: dict[str, Any] = MemoryAppConfig.model_json_schema()
        return JSONResponse(content=schema)

    return router
