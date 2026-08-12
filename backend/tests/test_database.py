from sqlalchemy import text
from app.core.database import engine

def test_database_connection() -> None:
    """
    Test that we can connect to the database and run a simple query.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar()
        assert value == 1
