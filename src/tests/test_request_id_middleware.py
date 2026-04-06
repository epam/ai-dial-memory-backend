"""Tests for request_id middleware — UUID injected into log context per request."""
from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pythonjsonlogger.json import JsonFormatter

from src.app.middleware.request_id import add_request_id_middleware


def _make_app_with_logging() -> tuple[FastAPI, StringIO]:
    """Return a FastAPI app with request_id middleware and a log-capturing endpoint."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter("%(name)s %(levelname)s %(message)s"))
    test_logger = logging.getLogger("test.request_id")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)

    app = FastAPI()
    add_request_id_middleware(app)

    @app.get("/ping")
    async def ping() -> dict:
        test_logger.info("handling request")
        return {"ok": True}

    return app, buf


@pytest.mark.asyncio
async def test_log_lines_within_request_carry_request_id() -> None:
    app, buf = _make_app_with_logging()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/ping")

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    assert lines, "No log lines captured"
    for line in lines:
        assert "request_id" in line, f"Log line missing request_id: {line}"


@pytest.mark.asyncio
async def test_different_requests_get_different_request_ids() -> None:
    app, buf = _make_app_with_logging()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/ping")
        await c.get("/ping")

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    ids = [l["request_id"] for l in lines if "request_id" in l]
    assert len(ids) >= 2
    assert ids[0] != ids[1], "Different requests must have different request_ids"


@pytest.mark.asyncio
async def test_request_id_is_a_uuid() -> None:
    import re
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    app, buf = _make_app_with_logging()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/ping")

    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip()]
    for line in lines:
        if "request_id" in line:
            assert uuid_re.match(line["request_id"]), f"Not a UUID: {line['request_id']}"
