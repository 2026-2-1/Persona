import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from persona.api import create_app, get_publisher
from persona.config import Settings
from persona.db import get_db
from persona.models import Base


def pytest_addoption(parser):
    parser.addoption("--run-browser", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-browser"):
        marker = pytest.mark.skip(reason="Use --run-browser after installing Chromium")
        for item in items:
            if "browser" in item.keywords:
                item.add_marker(marker)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, artifact_dir=tmp_path / "artifacts")


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def published():
    return []


@pytest.fixture
def client(db_factory, settings, published):
    application = create_app(settings)

    def database():
        with db_factory() as db:
            yield db

    application.dependency_overrides[get_db] = database
    application.dependency_overrides[get_publisher] = lambda: published.append
    with TestClient(application) as test_client:
        yield test_client
