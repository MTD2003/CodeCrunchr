from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app import app
from src.db import start_database_engine, get_session, run_migrations
from src.utils.env import get_required_env


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    return TestClient(app=app)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def initialized_test_db() -> AsyncGenerator[None, None]:
    start_database_engine(
        db_url = get_required_env("TEST_DATABASE_URL")
    )

    await run_migrations()

    yield


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def test_db(initialized_test_db: None) -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session