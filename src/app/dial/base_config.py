"""BaseApplicationTypeConfig — Pydantic base for schema-driven DIAL apps."""
from __future__ import annotations

import copy
import os
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from src.app.dial.dial_schema import DialJSONSchemaExtensions

# Internal markers injected by field factories into json_schema_extra.
# These are moved/renamed during model_json_schema() post-processing.
_KIND_MARKER = "x-dial-property-kind"
_RESOURCE_MARKER = "x-dial-resource"
_FILE_MARKER = "x-dial-file"
_PREVIEW_MARKER = "x-preview"


def _defined_in_class(cls: type, name: str) -> bool:
    """Return True if *name* was explicitly set in *cls*'s own class body.

    Pydantic v2 moves unannotated underscore attributes to ``__private_attributes__``
    early in ``ModelMetaclass.__new__``, before ``__init_subclass__`` fires.
    ClassVar-annotated class vars stay in ``cls.__dict__``.  We check both.
    """
    if name in getattr(cls, "__private_attributes__", {}):
        return True
    return name in cls.__dict__


class BaseApplicationTypeConfig(BaseModel):
    """Base class for all schema-driven DIAL application configs.

    Subclasses MUST define:
        _dial_schema_id: str          — unique ID in the DIAL schema registry
        _dial_application_type_display_name: str  — shown in the DIAL UI

    Subclasses MAY override:
        _dial_append_application_properties_header: bool  (default True)
    """

    _dial_schema_id: ClassVar[str]
    _dial_application_type_display_name: ClassVar[str]
    _dial_append_application_properties_header: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        has_id = _defined_in_class(cls, "_dial_schema_id")
        has_name = _defined_in_class(cls, "_dial_application_type_display_name")
        if has_id and not has_name:
            raise TypeError(
                f"{cls.__name__} defines _dial_schema_id but not "
                "_dial_application_type_display_name"
            )
        if has_name and not has_id:
            raise TypeError(
                f"{cls.__name__} defines _dial_application_type_display_name but not "
                "_dial_schema_id"
            )

    @classmethod
    def model_json_schema(cls, **kwargs: Any) -> dict[str, Any]:
        schema: dict[str, Any] = super().model_json_schema(**kwargs)
        schema = _flatten_ref(schema)
        schema = _strip_preview_fields(schema)
        schema = _inject_dial_meta(schema, list(cls.model_fields.keys()))
        schema = _add_dial_root_keys(schema, cls)
        return schema


# ---------------------------------------------------------------------------
# Field factories
# ---------------------------------------------------------------------------


def DialConfigField(
    default: Any,
    *,
    property_kind: str = "server",
    **kwargs: Any,
) -> Any:
    """Field with dial:propertyKind metadata (server = operator-only, client = user-editable)."""
    extra: dict[str, Any] = {_KIND_MARKER: property_kind}
    if "json_schema_extra" in kwargs:
        extra.update(kwargs.pop("json_schema_extra"))
    return Field(default, json_schema_extra=extra, **kwargs)


def DialResourceConfigField(default: Any, **kwargs: Any) -> Any:
    """Field that references a DIAL resource (marks dial:resource = true)."""
    extra: dict[str, Any] = {_RESOURCE_MARKER: True}
    if "json_schema_extra" in kwargs:
        extra.update(kwargs.pop("json_schema_extra"))
    return Field(default, json_schema_extra=extra, **kwargs)


def DialFileConfigField(default: Any, **kwargs: Any) -> Any:
    """Field that references a DIAL file (marks dial:file = true, format = dial-file-encoded)."""
    extra: dict[str, Any] = {_FILE_MARKER: True}
    if "json_schema_extra" in kwargs:
        extra.update(kwargs.pop("json_schema_extra"))
    return Field(default, json_schema_extra=extra, **kwargs)


def PreviewField(default: Any, **kwargs: Any) -> Any:
    """Field hidden from schema unless ENABLE_PREVIEW_FEATURES env var is set."""
    extra: dict[str, Any] = {_PREVIEW_MARKER: True}
    if "json_schema_extra" in kwargs:
        extra.update(kwargs.pop("json_schema_extra"))
    return Field(default, json_schema_extra=extra, **kwargs)


# ---------------------------------------------------------------------------
# Schema post-processing helpers
# ---------------------------------------------------------------------------


def _flatten_ref(schema: dict[str, Any]) -> dict[str, Any]:
    """If the schema has a top-level $ref, inline the referenced $defs entry."""
    ref = schema.get("$ref", "")
    if not ref.startswith("#/$defs/"):
        return schema
    def_name = ref[len("#/$defs/"):]
    defs: dict[str, Any] = schema.get("$defs", {})
    if def_name not in defs:
        return schema
    result = dict(defs[def_name])
    remaining = {k: v for k, v in defs.items() if k != def_name}
    if remaining:
        result["$defs"] = remaining
    return result


def _strip_preview_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove x-preview fields unless ENABLE_PREVIEW_FEATURES is set."""
    if os.environ.get("ENABLE_PREVIEW_FEATURES"):
        return schema
    props: dict[str, Any] = schema.get("properties", {})
    preview_keys = [k for k, v in props.items() if v.get(_PREVIEW_MARKER)]
    if not preview_keys:
        return schema
    schema = copy.deepcopy(schema)
    for key in preview_keys:
        del schema["properties"][key]
    required: list[str] = schema.get("required", [])
    schema["required"] = [r for r in required if r not in preview_keys]
    if not schema["required"]:
        schema.pop("required", None)
    return schema


def _inject_dial_meta(
    schema: dict[str, Any],
    field_order: list[str],
) -> dict[str, Any]:
    """Move internal markers into dial:meta and inject dial:propertyOrder."""
    schema = copy.deepcopy(schema)
    order_map = {name: idx for idx, name in enumerate(field_order)}
    for name, prop in schema.get("properties", {}).items():
        meta: dict[str, Any] = {}
        if _KIND_MARKER in prop:
            meta[DialJSONSchemaExtensions.PROPERTY_KIND] = prop.pop(_KIND_MARKER)
        meta[DialJSONSchemaExtensions.PROPERTY_ORDER] = order_map.get(name, 0)
        if _RESOURCE_MARKER in prop:
            prop[DialJSONSchemaExtensions.RESOURCE] = prop.pop(_RESOURCE_MARKER)
        if _FILE_MARKER in prop:
            prop[DialJSONSchemaExtensions.FILE] = prop.pop(_FILE_MARKER)
            prop["format"] = "dial-file-encoded"
        prop[DialJSONSchemaExtensions.META] = meta
    return schema


def _add_dial_root_keys(
    schema: dict[str, Any],
    cls: type[BaseApplicationTypeConfig],
) -> dict[str, Any]:
    """Inject DIAL-specific root keys into the schema."""
    schema = copy.deepcopy(schema)
    schema["$id"] = cls._dial_schema_id
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema[DialJSONSchemaExtensions.APPLICATION_TYPE_DISPLAY_NAME] = (
        cls._dial_application_type_display_name
    )
    schema[DialJSONSchemaExtensions.APPEND_APPLICATION_PROPERTIES_HEADER] = (
        cls._dial_append_application_properties_header
    )
    return schema
