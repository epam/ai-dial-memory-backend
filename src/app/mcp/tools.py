"""MCP tool registration via FastMCP (streamable HTTP transport)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.app.models.memory import MemoryType, StoreMemoryInput
from src.app.services.memory_service import MemoryService


def create_mcp_server(service: MemoryService) -> FastMCP:
    mcp: FastMCP = FastMCP("ai-dial-memory")

    @mcp.tool()
    async def store_memory(
        api_key: str,
        content: str,
        memory_type: MemoryType,
        context: str,
        importance: float,
    ) -> dict:
        """Store a new memory row."""
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
    async def search_archive(api_key: str, query: str) -> list[dict]:
        """Full-text search over episodic memories."""
        try:
            rows = await service.search_archive(api_key, query)
            return [r.model_dump(mode="json") for r in rows]
        except Exception as exc:
            return [{"error": str(exc)}]

    return mcp
