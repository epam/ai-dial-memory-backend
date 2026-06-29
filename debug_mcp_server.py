"""Minimal MCP debug server — one tool, logs Api-Key and bucket."""

import logging
import os
from typing import Any

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from aidial_client import AsyncDial
from fastapi import FastAPI
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DIAL_URL = os.environ.get("DIAL_URL", "http://host.docker.internal:8090")

mcp: FastMCP = FastMCP(
    "debug",
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def debug_tool(ctx: Context[Any, Any]) -> str:
    """Log Api-Key and resolve bucket/appdata from DIAL."""
    request = ctx.request_context.request
    api_key = request.headers.get("Api-Key") if request else None
    logger.debug("Api-Key: %s", api_key)
    logger.debug("All headers: %s", dict(request.headers) if request else {})

    if not api_key:
        return "error: Api-Key header missing"

    client = AsyncDial(api_key=api_key, base_url=DIAL_URL)
    raw = await client.bucket.get_raw()
    logger.debug("bucket response: %s", raw)

    if not raw.appdata:
        return f"bucket={raw.bucket}, appdata=None (missing)"

    storage_home = f"files/{raw.appdata}"
    logger.debug("storage_home: %s", storage_home)
    print(f"api_key={api_key}, bucket={raw.bucket}, storage_home={storage_home}")
    return "done"


if __name__ == "__main__":
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/mcp", mcp.streamable_http_app())
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
