"""MemoryAppConfig — schema-driven configuration for the AI DIAL Memory app."""
from __future__ import annotations

from app.dial.base_config import BaseApplicationTypeConfig, DialConfigField


class MemoryAppConfig(BaseApplicationTypeConfig):
    _dial_schema_id = "ai-dial-memory"
    _dial_application_type_display_name = "AI DIAL Memory"
    _dial_append_application_properties_header = True

    tier1_limit: int = DialConfigField(
        default=5,
        property_kind="client",
        description="Number of top-importance core memories to include in retrieval.",
    )
    tier2_limit: int = DialConfigField(
        default=10,
        property_kind="client",
        description="Number of episodic memories to include via full-text search.",
    )
