.PHONY: init_venv install_dev clean \
	format lint mypy test test_cov \
	black black_check isort isort_check autoflake autoflake_check flake8 \
	run_python dump_app_schema

SRC_DIRS = src/app src/scripts src/tests
MYPY_DIRS = src/app src/scripts
FILES ?= $(SRC_DIRS)

PYTHON ?= python3.13
ARGS ?=

init_venv:
	poetry env use $(PYTHON)

install_dev:
	poetry install

clean:
	-poetry env remove --all

# --- Linting ---

lint:
	poetry run flake8 $(FILES)
	poetry run black $(FILES) --check
	poetry run isort $(FILES) --check-only --diff
	poetry run autoflake $(FILES) --check
	poetry run mypy $(MYPY_DIRS)

mypy:
	poetry run mypy $(MYPY_DIRS)

# --- Formatting ---

format:
	poetry run autoflake $(FILES)
	poetry run black $(FILES)
	poetry run isort $(FILES)

# --- Individual tool targets (honor FILES variable) ---

black:
	poetry run black $(FILES)

black_check:
	poetry run black $(FILES) --check

isort:
	poetry run isort $(FILES)

isort_check:
	poetry run isort $(FILES) --check-only --diff

autoflake:
	poetry run autoflake $(FILES)

autoflake_check:
	poetry run autoflake $(FILES) --check

flake8:
	poetry run flake8 $(FILES)

# --- Running ---

run_python:
	$(if $(SCRIPT),,$(error SCRIPT is required, e.g. make run_python SCRIPT=path/to/script.py))
	poetry run python $(SCRIPT)

# --- Testing ---

test:
	poetry run pytest $(ARGS)

test_cov:
	poetry run pytest --cov=src/app --cov-report=term-missing $(ARGS)

# --- Schema ---

dump_app_schema:
	poetry run python src/scripts/dump_app_schema.py
