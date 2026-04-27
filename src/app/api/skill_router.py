"""Skill router — serves skill.md as a DIAL-prompt-compatible endpoint.

Quickapps fetches agent skills via ``client.prompts.get(url)`` which calls
``GET /v1/prompts/<api_path>`` and expects a DIAL Prompt JSON response.

The skill URL to use in the Quickapps config:
    prompts/appdata/ai-dial-memory/skill
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_SKILL_PATH = Path(__file__).parents[2] / "skill/skill.md"

_PROMPT_ID = "appdata/ai-dial-memory/skill"
_PROMPT_FOLDER_ID = "appdata/ai-dial-memory/skill"
_PROMPT_NAME = "skill"


def make_skill_router() -> APIRouter:
    router = APIRouter(prefix="/v1/prompts")

    @router.get("/appdata/ai-dial-memory/skill")
    async def get_skill() -> JSONResponse:
        """Return skill.md content in DIAL Prompt format."""
        content = _SKILL_PATH.read_text(encoding="utf-8")
        return JSONResponse(
            content={
                "id": _PROMPT_ID,
                "name": _PROMPT_NAME,
                "folderId": _PROMPT_FOLDER_ID,
                "content": content,
            }
        )

    return router
