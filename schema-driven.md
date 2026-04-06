# Schema-Driven DIAL Application — Architecture Guide

This document describes the full schema-driven pattern used in this project so it can be replicated in another DIAL application.

---

## Concept

A **schema-rich DIAL app** exposes a JSON Schema to DIAL Core. This schema describes the app's configurable properties. DIAL Core uses it to:
- Validate per-instance configuration (the `application_properties` JSON blob sent on every request)
- Power the UI editor for configuring app instances
- Enforce types and constraints before the app receives a request

The **single source of truth** is Python/Pydantic. No hand-written JSON schema exists — it is generated from the model tree.

---

## Key Files and Roles

### 1. Root Config Model — `src/quickapp/config/application.py`

The top-level Pydantic model that represents the full app configuration. Subclasses `BaseApplicationTypeConfig`.

```python
class ApplicationConfig(BaseApplicationTypeConfig):
    _dial_schema_id = "quickapps2"                         # unique ID in DIAL schema registry
    _dial_application_type_display_name = "Quick App 2.0"  # shown in DIAL UI
    _dial_append_application_properties_header = False

    orchestrator: OrchestratorConfig
    contexts: list[Context]
    tool_sets: list[ToolSet]
    # ... other fields
```

### 2. Base Config Class — `src/quickapp/common/base_config.py`

`BaseApplicationTypeConfig(BaseModel)` — the abstract base class every app type inherits. It:

- Declares required class vars (`_dial_schema_id`, `_dial_application_type_display_name`)
- Enforces these at class definition via `__init_subclass__`
- **Overrides `model_json_schema()`** to produce a DIAL-conformant schema:
  - Flattens the top-level `$ref` to inline the root definition
  - Strips `x-preview` fields when `ENABLE_PREVIEW_FEATURES` is not set
  - Injects `dial:meta` with `dial:propertyKind` and `dial:propertyOrder` on every root property
  - Adds DIAL root keys: `$id`, `$schema`, `dial:applicationTypeDisplayName`, etc.
  - Re-orders schema keys per `_schema_attributes_order`

### 3. DIAL Schema Extensions — `src/quickapp/common/dial_schema.py`

`DialJSONSchemaExtensions(StrEnum)` — all DIAL-specific JSON Schema extension keys:

| Key | Purpose |
|---|---|
| `dial:applicationTypeDisplayName` | Display name in DIAL UI |
| `dial:appendApplicationPropertiesHeader` | Whether to append app properties as a request header |
| `dial:applicationTypeCompletionEndpoint` | Chat completion endpoint URL |
| `dial:applicationTypeConfigurationEndpoint` | Configuration endpoint URL |
| `dial:applicationTypeSchemaEndpoint` | Live schema fetch URL |
| `dial:meta` | Per-property metadata object |
| `dial:propertyKind` | `"server"` (read-only, set by operator) or `"client"` (editable by user) |
| `dial:propertyOrder` | Integer ordering hint for UI rendering |
| `dial:resource` | Marks a string field as a DIAL resource reference |
| `dial:file` | Marks a string field as a DIAL file URL |

### 4. Custom Field Factories — `src/quickapp/common/base_config.py`

Use these instead of plain `pydantic.Field` to inject DIAL metadata:

```python
DialConfigField(default, property_kind="server"|"client")  # → dial:propertyKind
DialResourceConfigField(default)                            # → dial:resource: true
DialFileConfigField(default)                               # → dial:file: true, format: "dial-file-encoded"
PreviewField(default)                                      # → x-preview: true (stripped unless ENABLE_PREVIEW_FEATURES=true)
```

### 5. Schema Generation Script — `src/scripts/dump_app_schema.py`

Two modes:

- **Generate:** calls `ApplicationConfig.model_json_schema()`, prepends `dial:applicationTypeCompletionEndpoint` and `dial:applicationTypeConfigurationEndpoint` placeholders, writes to `docs/generated-app-schema.json`.
- **Check** (`--check`): regenerates in memory, compares to committed file, exits 1 if different (used in CI).

Run with `ENABLE_PREVIEW_FEATURES=true` so the committed schema always includes preview fields.

### 6. Committed Schema File — `docs/generated-app-schema.json`

The generated JSON schema checked into git. This is the artifact that gets embedded into DIAL Core config or referenced via the schema endpoint. Must be kept in sync with the model tree — enforced by CI.

### 7. Configuration Support Controller — `src/quickapp/configuration_support/_controller.py`

Registers live REST endpoints under `/v1/configuration-support/`:

| Endpoint | Description |
|---|---|
| `GET /v1/configuration-support/application-schema` | Live schema (without DIAL root fields) — used by DIAL Core |

The schema endpoint is registered in DIAL Core config as `dial:applicationTypeSchemaEndpoint`, allowing DIAL Core to always fetch the latest schema from the running instance without redeployment.

### 8. Runtime Validation — `src/quickapp/application/_request_context_setup.py`

On every request, the `application_properties` JSON blob is validated:

```python
application_config = ApplicationConfig.model_validate(application_properties)
```

Invalid configs raise Pydantic `ValidationError` before any business logic runs.

---

## Makefile Targets

```makefile
# Generate/update the committed schema file
dump_app_schema:
    ENABLE_PREVIEW_FEATURES=true poetry run python src/scripts/dump_app_schema.py docs/generated-app-schema.json

# Check schema is up to date (used in CI lint)
lint:
    ENABLE_PREVIEW_FEATURES=true poetry run python src/scripts/dump_app_schema.py docs/generated-app-schema.json --check

# Regenerate schema as part of formatting (only when formatting all src dirs)
format:
    ENABLE_PREVIEW_FEATURES=true poetry run python src/scripts/dump_app_schema.py docs/generated-app-schema.json
```

---

## DIAL Core Integration

Two ways to register the app schema with DIAL Core:

**Option A — Live schema endpoint (recommended):**
```json
{
  "dial:applicationTypeSchemaEndpoint": "<quickapps_base_url>/v1/configuration-support/application-schema"
}
```
DIAL Core fetches the schema dynamically. No need to copy schema files on updates.

**Option B — Embedded schema:**
Paste the full content of `docs/generated-app-schema.json` into the `applicationTypeSchemas` array in DIAL Core config. See `docker_compose_files/core/configuration/generated/application-schemas.json` for an example.

Also required in DIAL Core settings:
```json
{ "applications": { "includeCustomApps": true } }
```

---

## How to Add a New Configurable Field

1. Add a Pydantic field to the appropriate model (or `ApplicationConfig` directly).
2. Use `DialConfigField(...)` with the correct `property_kind` (`"server"` for operator-only, `"client"` for user-editable).
3. For preview-only fields, use `PreviewField(...)`.
4. Run `make dump_app_schema` to regenerate `docs/generated-app-schema.json`.
5. Commit both the model change and the updated schema file.

---

## CI Enforcement

`.github/workflows/pr.yml` delegates to a reusable workflow that runs `make lint`. This includes the schema drift check — if `docs/generated-app-schema.json` is out of date with the current models, the PR fails.

---

## Dependencies (pyproject.toml)

```toml
pydantic = ">=2.12.4,<3.0.0"          # schema generation engine
pydantic-settings = ">=2.12.0,<3.0.0"  # settings models
aidial-sdk = { extras = ["telemetry"], version = ">=0.32.0,<0.33.0" }  # DIALApp, ConfigurationRequest/Response

[tool.mypy]
plugins = ["pydantic.mypy"]             # type-check schema models correctly
```
