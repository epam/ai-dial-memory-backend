"""MCP tool registration via FastMCP (streamable HTTP transport)."""
from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from src.app.models.memory import MemoryType, StoreMemoryInput
from src.app.storage.common.memory_service import AbstractMemoryService


def _get_api_key(ctx: Context) -> str | None:
    """Extract Api-Key from the HTTP request headers."""
    return ctx.request_context.request.headers.get("Api-Key")


def create_mcp_server(service: AbstractMemoryService) -> FastMCP:
    mcp: FastMCP = FastMCP(
        "ai-dial-memory",
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    async def store_memory(
        content: str,
        memory_type: MemoryType,
        context: str,
        importance: float,
        ctx: Context,
    ) -> dict:
        """Store a new memory row."""
        api_key = _get_api_key(ctx)
        if not api_key:
            return {"error": "Api-Key header missing", "status": 401}
        try:
            result = await service.store(
                api_key,
                StoreMemoryInput(
                    content=content,
                    memory_type=memory_type,
                    context=context,
                    importance=importance,
                ),
            )
            return {"id": result.id, "stored": result.stored}
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool()
    async def search_archive(query: str, ctx: Context) -> list[dict]:
        """Full-text search over episodic memories."""
        api_key = _get_api_key(ctx)
        if not api_key:
            return [{"error": "Api-Key header missing", "status": 401}]
        try:
            rows = await service.search_archive(api_key, query)
            return [r.model_dump(mode="json") for r in rows]
        except Exception as exc:
            return [{"error": str(exc)}]

    @mcp.tool(name="prime_memories")
    async def prime_memories(
        ctx: Context,
        app_name: str | None = None,
    ) -> list[dict]:
        """Return top core memories plus episodic memories scoped to the given
        app/deployment name. Designed as a synthetic tool call — inject at the
        start of every dialogue."""
        api_key = _get_api_key(ctx)
        if not api_key:
            return [{"error": "Api-Key header missing", "status": 401}]
        try:
            response = await service.retrieve(api_key, app_name)
            return [r.model_dump(mode="json") for r in response.facts]
        except Exception as exc:
            return [{"error": str(exc)}]

    return mcp
