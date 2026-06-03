"""Request-ID middleware — injects a UUID into every log record for each request."""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Patch LogRecord factory once so request_id is present on every record.
_original_factory = logging.getLogRecordFactory()


def _record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    record = _original_factory(*args, **kwargs)
    record.request_id = _request_id_var.get("")
    return record


logging.setLogRecordFactory(_record_factory)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = str(uuid.uuid4())
        token = _request_id_var.set(rid)
        try:
            return await call_next(request)
        finally:
            _request_id_var.reset(token)


def add_request_id_middleware(app: FastAPI) -> None:
    """Register the RequestIdMiddleware on the given FastAPI app."""
    app.add_middleware(RequestIdMiddleware)
