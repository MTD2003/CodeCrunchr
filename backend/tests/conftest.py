import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app=app)
