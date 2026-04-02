"""Production entrypoint: logging → DI → FastAPI → Uvicorn."""
from __future__ import annotations

import uvicorn
from injector import Injector
from fastapi import FastAPI

from app.config.app_settings import AppSettings
from app.config.logging_config import setup_logging
from app.di.app_module import AppModule


def main() -> None:
    settings = AppSettings()
    setup_logging(settings)

    injector = Injector([AppModule()])
    app = injector.get(FastAPI)

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
