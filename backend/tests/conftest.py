"""Shared backend test fixtures."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import create_application


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Construct a test client for backend tests."""
    app = create_application()
    with TestClient(app) as test_client:
        yield test_client


def create_test_client() -> TestClient:
    """Construct a test client for backend tests."""
    return TestClient(create_application())
