from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryType = Literal["core", "episodic"]


class MemoryRow(BaseModel):
    id: str
    memory_type: MemoryType
    content: str
    context: str
    importance: float
    embedding_model: str | None = None
    vector: list[float] | None = None
    timestamp: datetime.datetime
    access_count: int


class StoreMemoryInput(BaseModel):
    content: str
    memory_type: MemoryType
    context: str
    importance: float = Field(ge=0.0, le=1.0)


class StoreMemoryOutput(BaseModel):
    id: str
    stored: bool


class RetrieveRequest(BaseModel):
    query: str
    tier1_limit: int = 5
    tier2_limit: int = 10


class RetrieveResponse(BaseModel):
    facts: list[MemoryRow] = Field(default_factory=list)
