"""DIAL-specific JSON Schema extension keys."""

from __future__ import annotations

from enum import StrEnum


class DialJSONSchemaExtensions(StrEnum):
    APPLICATION_TYPE_DISPLAY_NAME = "dial:applicationTypeDisplayName"
    APPEND_APPLICATION_PROPERTIES_HEADER = "dial:appendApplicationPropertiesHeader"
    APPLICATION_TYPE_COMPLETION_ENDPOINT = "dial:applicationTypeCompletionEndpoint"
    APPLICATION_TYPE_CONFIGURATION_ENDPOINT = (
        "dial:applicationTypeConfigurationEndpoint"
    )
    APPLICATION_TYPE_SCHEMA_ENDPOINT = "dial:applicationTypeSchemaEndpoint"
    META = "dial:meta"
    PROPERTY_KIND = "dial:propertyKind"
    PROPERTY_ORDER = "dial:propertyOrder"
    RESOURCE = "dial:resource"
    FILE = "dial:file"
