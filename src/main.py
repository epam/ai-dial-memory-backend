"""Production entrypoint: logging → DI → FastAPI → Uvicorn."""

from __future__ import annotations

import uvicorn
from injector import Injector
from fastapi import FastAPI

from src.app.di.app_module import AppModule
from src.app.config.app_settings import AppSettings
from src.app.config.logging_config import setup_logging


def main() -> None:
    settings = AppSettings()
    setup_logging(settings)

    injector = Injector([AppModule()])
    app = injector.get(FastAPI)

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
