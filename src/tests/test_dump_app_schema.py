"""Tests for the schema dump script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = str(_PROJECT_ROOT / "src" / "scripts" / "dump_app_schema.py")


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _SCRIPT, *args],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )


def test_generates_valid_json_to_output_file(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    result = _run(str(output))
    assert result.returncode == 0, result.stderr
    assert output.exists()
    schema = json.loads(output.read_text())
    assert "properties" in schema
    assert "tier1_limit" in schema["properties"]
    assert "tier2_limit" in schema["properties"]


def test_check_mode_passes_when_file_is_current(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    _run(str(output))
    result = _run(str(output), "--check")
    assert result.returncode == 0, result.stderr


def test_check_mode_fails_when_file_is_stale(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    output.write_text('{"stale": true}\n')
    result = _run(str(output), "--check")
    assert result.returncode == 1


def test_check_mode_fails_when_file_missing(tmp_path: Path) -> None:
    output = tmp_path / "missing-schema.json"
    result = _run(str(output), "--check")
    assert result.returncode == 1


def test_generated_schema_includes_preview_fields(tmp_path: Path) -> None:
    """Dump script always generates with ENABLE_PREVIEW_FEATURES=true."""
    output = tmp_path / "schema.json"
    _run(str(output))
    schema = json.loads(output.read_text())
    assert "$id" in schema
