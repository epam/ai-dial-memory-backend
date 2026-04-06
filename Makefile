.PHONY: dump_app_schema lint format test

## Regenerate docs/generated-app-schema.json from the current Pydantic model tree.
dump_app_schema:
	ENABLE_PREVIEW_FEATURES=true poetry run python scripts/dump_app_schema.py docs/generated-app-schema.json

## Lint: check schema is up to date, run ruff, run mypy.
lint:
	ENABLE_PREVIEW_FEATURES=true poetry run python scripts/dump_app_schema.py docs/generated-app-schema.json --check
	poetry run ruff check .
	poetry run mypy .

## Format: regenerate schema + ruff format.
format:
	ENABLE_PREVIEW_FEATURES=true poetry run python scripts/dump_app_schema.py docs/generated-app-schema.json
	poetry run ruff format .

## Run the test suite.
test:
	poetry run pytest
