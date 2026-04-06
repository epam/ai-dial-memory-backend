"""Tests for main.py entrypoint — logging setup, DI wiring, Uvicorn start."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_main_calls_logging_setup_then_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")

    call_order: list[str] = []

    mock_setup = MagicMock(side_effect=lambda s: call_order.append("logging"))
    mock_uvicorn_run = MagicMock(side_effect=lambda app, host, port: call_order.append("uvicorn"))

    with (
        patch("src.main.setup_logging", mock_setup),
        patch("src.main.uvicorn.run", mock_uvicorn_run),
    ):
        from src import main as m
        m.main()

    assert call_order[0] == "logging", "setup_logging must be called before uvicorn.run"
    assert "uvicorn" in call_order


def test_main_passes_host_and_port_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIAL_URL", "http://dial.test")
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "9000")

    uvicorn_calls: list[dict] = []

    def _capture(app, host, port):  # noqa: ANN001
        uvicorn_calls.append({"host": host, "port": port})

    with (
        patch("src.main.setup_logging"),
        patch("src.main.uvicorn.run", side_effect=_capture),
    ):
        from src import main as m
        m.main()

    assert uvicorn_calls, "uvicorn.run was not called"
    assert uvicorn_calls[0]["host"] == "0.0.0.0"
    assert uvicorn_calls[0]["port"] == 9000
