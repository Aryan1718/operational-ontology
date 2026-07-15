"""Shared backend test fixtures."""

from fastapi.testclient import TestClient

from app.main import create_application


def create_test_client() -> TestClient:
    """Construct a test client for backend tests."""
    return TestClient(create_application())
