# Code style and module organization

This document describes how the application is structured and how to add or change code in a consistent way. It is aimed at newcomers and contributors.

---

## 1. Dependency Injection (injector)

**All interactions between modules should go through Dependency Injection.** We use the [injector](https://github.com/python-injector/injector) library (with [fastapi-injector](https://github.com/abstractkitchen/fastapi-injector) for FastAPI).

### Rules

- **Do not** import and instantiate another module's services or config in business code. Request them via constructor parameters and let the injector provide them.
- **Do** define one **module class** per feature (e.g. `DialModule`, `LanceModule`). The module's `configure(binder)` method declares how types are bound (to which implementation, in which scope).
- **Do** use the `@inject` decorator on classes that receive injected dependencies, and declare dependencies in `__init__`; the injector will resolve them when creating the instance.
- **Do** use `@provider` / `@multiprovider` in the module when the injector needs custom logic to create an instance (e.g. depending on other injected types).

### Where it's wired

- **`app_module.py`** builds the root `Injector` by installing all feature modules (`DialModule`, `LanceModule`, etc.).
- Each **`*_module.py`** (e.g. `dial_module.py`, `lance/module.py`) defines a class that extends `injector.Module` and in `configure()` binds interfaces/classes to implementations and scopes (`singleton`, `noscope`, etc.).

### Example (consumer)

```python
# src/app/storage/lance/sync.py
from injector import inject

@inject
class StorageSync:
    def __init__(
        self,
        dial_storage_service: DialStorageService,
        settings: AppSettings,
    ) -> None:
        self._dial = dial_storage_service
        self._settings = settings
```

`StorageSync` does not import or construct `AppSettings`; the injector passes it in.

### Example (module binding)

```python
# src/app/storage/lance/module.py
class LanceModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(MemoryRepository, to=LanceDbMemoryRepository, scope=noscope)
        binder.bind(StorageSync, to=StorageSync, scope=singleton)
        binder.bind(AbstractMemoryService, to=MemoryService, scope=singleton)
```

### Example (top-level wiring)

```python
# src/app/di/app_module.py
class AppModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.install(DialModule())
        binder.install(LanceModule())
```

---

## 2. Per-module settings (environment variables)

**If a module depends on environment variables, it must have its own settings class and use it via DI.** Do not read `os.getenv` (or `os.environ`) in business code or in random modules.

### Rules

- **One settings class per (injector) module** that needs config (e.g. `AppSettings`). Name it `{ModuleName}Settings` when it belongs to a feature module.
- **Define it in (or next to) that module** (e.g. `config/app_settings.py`).
- Use **pydantic-settings** (`BaseSettings`) for the class. Use `Field(..., alias="ENV_VAR_NAME")` so existing env var names are supported.
- **Bind the settings class in that module's `configure()`** (e.g. `binder.bind(AppSettings, to=AppSettings, scope=singleton)`). Consumers receive the same instance via constructor injection.
- **Do not** add `os.getenv` / `os.environ` in application or tooling code. The only place that should read env for app config is inside the settings classes.
- **Document** the purpose and default of each env variable in the settings class.

### Example (settings class)

```python
# src/app/config/app_settings.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True)

    dial_url: str = Field(alias="DIAL_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tmp_dir: Path = Field(default=Path("/tmp"), alias="TMP_DIR")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
```

### Example (module binding and use)

In the module's `configure()`:

```python
binder.bind(AppSettings, to=AppSettings, scope=singleton)
```

In a class that needs these settings:

```python
@inject
def __init__(self, dial_storage_service: DialStorageService, settings: AppSettings) -> None:
    self._settings = settings
```

---

## 3. Encapsulation and visibility

- **Protected by default**: Use a single leading underscore (`_`) for class attributes and methods that are internal to the class or module.
- **Public only when needed**: Expose public attributes (no underscore) only when they are part of the intended external API.
- This keeps the public surface small and makes refactoring safer.

---

## 4. Types and clarity

- **Type hints**: Use type hints on function and method signatures (parameters and return types) so readers and tools (IDEs, linters) understand expected types.
- **Modern built-in generics**: Prefer built-in generics over `typing` aliases where possible:
  - `list[str]`, `dict[str, int]`, `tuple[str, float]` instead of `List`, `Dict`, `Tuple`.
  - For unions in Python 3.10+, use `str | None` instead of `Optional[str]`.
- **Complex or ambiguous cases**: Add a short docstring to clarify meaning or constraints.
- **Factory methods**: For a `@classmethod` that acts as a factory, use `typing.Self` as the return type.

---

## 5. Naming

- **Functions and methods**: `snake_case`.
- **Classes**: `PascalCase` (e.g. `AppSettings`, `StorageSync`, `LanceModule`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g. `DEFAULT_LOG_LEVEL`).
- **Modules**: `snake_case` filenames (e.g. `app_settings.py`, `dial_module.py`).

---

## 6. Code organization and imports

- **Logical separation**: Group related classes and functions into modules. Each module should have a clear purpose or feature.
- **Explicit imports**: Avoid `from module import *`. Import only what you use.
- **Import order**: Standard library → third-party → local/project modules, with a blank line between each group.

---

## 7. Class bodies and global state

- **No conditional or complex logic in class bodies**: Do not put conditionals or non-trivial logic at class level (e.g. `if condition: x = ...`). Use constants, `__init__`, factory functions, or helper functions instead.
- **Avoid mutable global state**: Prefer passing mutable objects as parameters. If global or shared state is necessary, document it and ensure thread-safe access where relevant.

---

## 8. Pydantic: validation and complex arguments

- **Validation**: Use Pydantic models for structured data validation instead of ad-hoc checks. Prefer `MyModel.model_validate(data)` over manual validation of dicts.
- **Complex arguments**: Prefer Pydantic models (or typed structures) for complex function arguments instead of `dict[str, Any]` or nested dicts when the shape is fixed. Using `dict` is fine when keys and values are homogeneous (e.g. a mapping from id to a known type).
- **Mutable defaults in Pydantic**: Do not use mutable default values (e.g. `items: list[str] = []`). Use `Field(default_factory=list)` (or similar) instead.

### Example (parsing a request header)

```python
# src/app/middleware/app_config.py
data = json.loads(header_value)
return MemoryAppConfig.model_validate(data)
```

### Example (converting a raw DB record)

```python
# src/app/storage/lance/repository.py
return MemoryRow.model_validate(clean)
```

---

## 9. Logging and error handling

- **Use the logging module**: Use Python's `logging` instead of `print()` for production behavior. Instantiate a module-level logger via `logging.getLogger(__name__)`. Configure log levels via `AppSettings` / `LOG_LEVEL`.
- **Graceful error handling**: Use exceptions where appropriate. Avoid silent failures; log or re-raise with clear messages so issues are visible and debuggable.

### Example

```python
# src/app/dial/dial_storage.py
logger = logging.getLogger(__name__)

logger.info("resolved storage home: %s", home)
logger.debug("download start: %s → %s", remote_url, local_path)
logger.error("download failed: %s — %s", remote_url, exc)
```

---

## 10. Linters and formatters

The project uses **black**, **isort**, **flake8**, **autoflake**, and **mypy**. Run `make lint` before submitting changes and `make format` to auto-fix style issues.

| Tool | Purpose | Command |
|---|---|---|
| `black` | Code formatting | `make black` |
| `isort` | Import sorting | `make isort` |
| `flake8` | Style and error linting | `make flake8` |
| `autoflake` | Remove unused imports/variables | `make autoflake` |
| `mypy` | Static type checking | `make mypy` |

---

## 11. Dependencies

- **Declare direct dependencies**: Any package that is directly imported in the codebase must be declared as a dependency in `pyproject.toml`. Do not rely on transitive dependencies for direct imports.

---

## 12. Summary checklist

- **DI**: Cross-module use of services or config goes through constructor injection; types are bound in a module's `configure()`; no direct instantiation of other modules' types in business code.
- **Env**: Env-based config lives in a pydantic-settings class (e.g. `AppSettings`), bound in the injector and injected; no `os.getenv` in application/tooling code.
- **Naming**: Module class `XxxModule`, settings class `XxxSettings`, env names preserved via `Field(alias="ENV_VAR_NAME")`.
- **Visibility**: Prefer protected (`_`) for internals; public only for the intended API.
- **Types**: Use type hints and modern generics; use Pydantic for validation and complex arguments; avoid mutable defaults in Pydantic fields.
- **Structure**: Clear module boundaries, explicit imports, no complex logic in class bodies, logging instead of print, declared dependencies.
