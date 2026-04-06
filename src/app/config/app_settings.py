from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True)

    dial_url: str = Field(alias="DIAL_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tmp_dir: Path = Field(default=Path("/tmp"), alias="TMP_DIR")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
