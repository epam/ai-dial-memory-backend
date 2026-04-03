"""Tests for the schema dump script."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_generates_valid_json_to_output_file(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    result = subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()
    schema = json.loads(output.read_text())
    assert "properties" in schema
    assert "tier1_limit" in schema["properties"]
    assert "tier2_limit" in schema["properties"]


def test_check_mode_passes_when_file_is_current(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output)],
        check=True,
    )
    result = subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_check_mode_fails_when_file_is_stale(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    output.write_text('{"stale": true}\n')
    result = subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_check_mode_fails_when_file_missing(tmp_path: Path) -> None:
    output = tmp_path / "missing-schema.json"
    result = subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_generated_schema_includes_preview_fields(tmp_path: Path) -> None:
    """Dump script always generates with ENABLE_PREVIEW_FEATURES=true."""
    output = tmp_path / "schema.json"
    subprocess.run(
        [sys.executable, "scripts/dump_app_schema.py", str(output)],
        check=True,
    )
    schema = json.loads(output.read_text())
    assert "$id" in schema
