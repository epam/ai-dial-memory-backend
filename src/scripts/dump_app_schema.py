#!/usr/bin/env python3
"""Dump the MemoryAppConfig JSON schema to a file, or check for schema drift.

Usage:
    # Generate / update committed schema file
    ENABLE_PREVIEW_FEATURES=true python scripts/dump_app_schema.py docs/generated-app-schema.json

    # Check that committed file is up to date (used in CI)
    ENABLE_PREVIEW_FEATURES=true python scripts/dump_app_schema.py docs/generated-app-schema.json --check
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `app` is importable when the script
# is run directly (e.g. `python scripts/dump_app_schema.py ...`).
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Enable preview features before importing the config so the schema is complete.
os.environ.setdefault("ENABLE_PREVIEW_FEATURES", "true")

# Must come after env-var setup so model_json_schema() sees the flag.
from src.app.config.application import MemoryAppConfig  # noqa: E402


def _generate_schema_json() -> str:
    schema = MemoryAppConfig.model_json_schema()
    return json.dumps(schema, indent=2) + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: dump_app_schema.py <output_file> [--check]",
            file=sys.stderr,
        )
        sys.exit(1)

    output_path = Path(sys.argv[1])
    check_mode = "--check" in sys.argv[2:]
    schema_json = _generate_schema_json()

    if check_mode:
        if not output_path.exists():
            print(f"Schema file not found: {output_path}", file=sys.stderr)
            sys.exit(1)
        current = output_path.read_text(encoding="utf-8")
        if current != schema_json:
            print(
                f"Schema drift detected: {output_path} is out of date.\n"
                "Run: ENABLE_PREVIEW_FEATURES=true python scripts/dump_app_schema.py "
                f"{output_path}  to update.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Schema is up to date: {output_path}")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(schema_json, encoding="utf-8")
        print(f"Schema written to {output_path}")


if __name__ == "__main__":
    main()
