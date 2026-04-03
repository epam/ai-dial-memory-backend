"""Tests for DialJSONSchemaExtensions enum."""
from __future__ import annotations

from app.dial.dial_schema import DialJSONSchemaExtensions


def test_all_keys_have_dial_prefix() -> None:
    for member in DialJSONSchemaExtensions:
        assert member.value.startswith("dial:"), (
            f"{member.name} has value {member.value!r}, expected 'dial:' prefix"
        )


def test_known_keys_present() -> None:
    values = {m.value for m in DialJSONSchemaExtensions}
    assert "dial:applicationTypeDisplayName" in values
    assert "dial:appendApplicationPropertiesHeader" in values
    assert "dial:applicationTypeCompletionEndpoint" in values
    assert "dial:applicationTypeConfigurationEndpoint" in values
    assert "dial:applicationTypeSchemaEndpoint" in values
    assert "dial:meta" in values
    assert "dial:propertyKind" in values
    assert "dial:propertyOrder" in values
    assert "dial:resource" in values
    assert "dial:file" in values


def test_members_are_strings() -> None:
    for member in DialJSONSchemaExtensions:
        assert isinstance(member.value, str)
