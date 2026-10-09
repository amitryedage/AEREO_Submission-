"""Global pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from certgen.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a test client for the FastAPI application."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
