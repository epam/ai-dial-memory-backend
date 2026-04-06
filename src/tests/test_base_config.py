"""Tests for BaseApplicationTypeConfig and custom field factories."""
from __future__ import annotations

import pytest

from src.app.dial.base_config import (
    BaseApplicationTypeConfig,
    DialConfigField,
    DialFileConfigField,
    DialResourceConfigField,
    PreviewField,
)
from src.app.dial.dial_schema import DialJSONSchemaExtensions


class _SampleConfig(BaseApplicationTypeConfig):
    _dial_schema_id = "test-app"
    _dial_application_type_display_name = "Test App"

    name: str = DialConfigField(default="hello", property_kind="client")
    score: float = DialConfigField(default=0.5, property_kind="server")


# ---------------------------------------------------------------------------
# __init_subclass__ enforcement
# ---------------------------------------------------------------------------


def test_init_subclass_raises_when_only_display_name_defined() -> None:
    with pytest.raises(TypeError, match="_dial_schema_id"):

        class _Bad(BaseApplicationTypeConfig):  # type: ignore[misc]
            _dial_application_type_display_name = "Bad"
            value: str = "x"


def test_init_subclass_raises_when_only_schema_id_defined() -> None:
    with pytest.raises(TypeError, match="_dial_application_type_display_name"):

        class _Bad2(BaseApplicationTypeConfig):  # type: ignore[misc]
            _dial_schema_id = "bad"
            value: str = "x"


def test_init_subclass_allows_class_with_neither_defined() -> None:
    """Intermediate/abstract classes defining neither var are allowed."""

    class _Abstract(BaseApplicationTypeConfig):  # type: ignore[misc]
        pass

    assert issubclass(_Abstract, BaseApplicationTypeConfig)


# ---------------------------------------------------------------------------
# DIAL root keys in generated schema
# ---------------------------------------------------------------------------


def test_schema_contains_dollar_id() -> None:
    schema = _SampleConfig.model_json_schema()
    assert schema["$id"] == "test-app"


def test_schema_contains_dollar_schema() -> None:
    schema = _SampleConfig.model_json_schema()
    assert "$schema" in schema


def test_schema_contains_display_name() -> None:
    schema = _SampleConfig.model_json_schema()
    assert schema[DialJSONSchemaExtensions.APPLICATION_TYPE_DISPLAY_NAME] == "Test App"


def test_schema_contains_append_header_flag() -> None:
    schema = _SampleConfig.model_json_schema()
    assert DialJSONSchemaExtensions.APPEND_APPLICATION_PROPERTIES_HEADER in schema


# ---------------------------------------------------------------------------
# dial:meta injection via field factories
# ---------------------------------------------------------------------------


def test_dial_config_field_client_kind_in_schema() -> None:
    schema = _SampleConfig.model_json_schema()
    meta = schema["properties"]["name"][DialJSONSchemaExtensions.META]
    assert meta[DialJSONSchemaExtensions.PROPERTY_KIND] == "client"


def test_dial_config_field_server_kind_in_schema() -> None:
    schema = _SampleConfig.model_json_schema()
    meta = schema["properties"]["score"][DialJSONSchemaExtensions.META]
    assert meta[DialJSONSchemaExtensions.PROPERTY_KIND] == "server"


def test_dial_meta_includes_property_order() -> None:
    schema = _SampleConfig.model_json_schema()
    for field_name in ("name", "score"):
        meta = schema["properties"][field_name][DialJSONSchemaExtensions.META]
        assert DialJSONSchemaExtensions.PROPERTY_ORDER in meta


def test_property_order_follows_declaration_order() -> None:
    schema = _SampleConfig.model_json_schema()
    name_order = schema["properties"]["name"][DialJSONSchemaExtensions.META][
        DialJSONSchemaExtensions.PROPERTY_ORDER
    ]
    score_order = schema["properties"]["score"][DialJSONSchemaExtensions.META][
        DialJSONSchemaExtensions.PROPERTY_ORDER
    ]
    assert name_order < score_order


# ---------------------------------------------------------------------------
# Preview fields
# ---------------------------------------------------------------------------


def test_preview_field_excluded_without_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_PREVIEW_FEATURES", raising=False)

    class _WithPreview(BaseApplicationTypeConfig):
        _dial_schema_id = "preview-app"
        _dial_application_type_display_name = "Preview App"

        hidden: str = PreviewField(default="x")
        visible: str = DialConfigField(default="y", property_kind="client")

    schema = _WithPreview.model_json_schema()
    assert "hidden" not in schema.get("properties", {})
    assert "visible" in schema.get("properties", {})


def test_preview_field_included_with_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_PREVIEW_FEATURES", "true")

    class _WithPreview2(BaseApplicationTypeConfig):
        _dial_schema_id = "preview-app-2"
        _dial_application_type_display_name = "Preview App 2"

        hidden: str = PreviewField(default="x")

    schema = _WithPreview2.model_json_schema()
    assert "hidden" in schema.get("properties", {})


# ---------------------------------------------------------------------------
# Resource / File field factories
# ---------------------------------------------------------------------------


def test_dial_resource_field_marks_resource_in_schema() -> None:
    class _ResourceConfig(BaseApplicationTypeConfig):
        _dial_schema_id = "resource-app"
        _dial_application_type_display_name = "Resource App"

        res: str = DialResourceConfigField(default="some/path")

    schema = _ResourceConfig.model_json_schema()
    assert schema["properties"]["res"].get(DialJSONSchemaExtensions.RESOURCE) is True


def test_dial_file_field_marks_file_and_format_in_schema() -> None:
    class _FileConfig(BaseApplicationTypeConfig):
        _dial_schema_id = "file-app"
        _dial_application_type_display_name = "File App"

        doc: str = DialFileConfigField(default="files/abc/doc.pdf")

    schema = _FileConfig.model_json_schema()
    prop = schema["properties"]["doc"]
    assert prop.get(DialJSONSchemaExtensions.FILE) is True
    assert prop.get("format") == "dial-file-encoded"
