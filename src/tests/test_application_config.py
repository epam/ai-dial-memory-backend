"""Tests for MemoryAppConfig."""
from __future__ import annotations

from src.app.config.application import MemoryAppConfig
from src.app.dial.dial_schema import DialJSONSchemaExtensions


def test_default_tier1_limit() -> None:
    assert MemoryAppConfig().tier1_limit == 5


def test_default_tier2_limit() -> None:
    assert MemoryAppConfig().tier2_limit == 10


def test_override_limits() -> None:
    cfg = MemoryAppConfig(tier1_limit=3, tier2_limit=7)
    assert cfg.tier1_limit == 3
    assert cfg.tier2_limit == 7


def test_model_validate_from_dict() -> None:
    cfg = MemoryAppConfig.model_validate({"tier1_limit": 2, "tier2_limit": 4})
    assert cfg.tier1_limit == 2
    assert cfg.tier2_limit == 4


def test_model_validate_empty_dict_uses_defaults() -> None:
    cfg = MemoryAppConfig.model_validate({})
    assert cfg.tier1_limit == 5
    assert cfg.tier2_limit == 10


def test_schema_has_tier1_limit_property() -> None:
    assert "tier1_limit" in MemoryAppConfig.model_json_schema()["properties"]


def test_schema_has_tier2_limit_property() -> None:
    assert "tier2_limit" in MemoryAppConfig.model_json_schema()["properties"]


def test_schema_tier_limits_are_client_properties() -> None:
    schema = MemoryAppConfig.model_json_schema()
    for field in ("tier1_limit", "tier2_limit"):
        meta = schema["properties"][field][DialJSONSchemaExtensions.META]
        assert meta[DialJSONSchemaExtensions.PROPERTY_KIND] == "client"


def test_schema_has_dial_id() -> None:
    assert "$id" in MemoryAppConfig.model_json_schema()


def test_schema_has_display_name() -> None:
    schema = MemoryAppConfig.model_json_schema()
    assert schema.get(DialJSONSchemaExtensions.APPLICATION_TYPE_DISPLAY_NAME)
