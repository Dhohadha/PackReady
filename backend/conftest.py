import os
import pytest

# Point tests to dedicated PostgreSQL test database so main dev database is never wiped
os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5433/packready_test"

from app.core.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
