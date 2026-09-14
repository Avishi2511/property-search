"""Shared test fixtures.

Extraction tests must be deterministic regardless of whether the machine
running them happens to have a real GEMINI_API_KEY set, so we force Gemini
off for the whole test session and test the rule-based path explicitly.
Gemini-specific behavior (when it's wired in) gets its own mocked tests.
"""
import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def disable_gemini(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
