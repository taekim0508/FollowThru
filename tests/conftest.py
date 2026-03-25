from __future__ import annotations

import os
os.environ.setdefault("AI_PROVIDER", "mock")  # must be set before app.config is imported

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session

from app.database import get_session
from app.main import app


TEST_DATABASE_URL = "sqlite://"  # in-memory


@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Ensure all models are imported so metadata is populated
    from app import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session", scope="function")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client", scope="function")
def client_fixture(engine):
    def _get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_test_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
