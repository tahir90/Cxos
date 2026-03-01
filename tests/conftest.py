"""Pytest configuration — set test env before any imports."""

import os

# Ensure rate limiting and production checks are disabled in tests
os.environ.setdefault("CXO_ENV", "test")
