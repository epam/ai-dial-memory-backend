"""Tests for memory Pydantic models."""
from src.app.models.memory import RetrieveRequest


def test_retrieve_request_defaults_app_name_to_none():
    req = RetrieveRequest()
    assert req.app_name is None
    assert req.tier1_limit == 5
    assert req.tier2_limit == 10


def test_retrieve_request_accepts_app_name():
    req = RetrieveRequest(app_name="my-dial-app")
    assert req.app_name == "my-dial-app"
