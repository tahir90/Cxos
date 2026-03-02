"""Pytest configuration — set test env before any imports."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure rate limiting and production checks are disabled in tests
os.environ.setdefault("CXO_ENV", "test")

# LLM required for chat — use dummy key so HAS_LLM is True
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI API calls so tests run without real API."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I understand. How can I help you today?"

    with patch("openai.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_client_cls.return_value = mock_client
        yield mock_client
