import pytest
import tempfile
from pathlib import Path
from datetime import date, timedelta


@pytest.fixture
def tmp_db(tmp_path):
    from daymark.db.database import Database
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def today():
    return date.today().isoformat()


@pytest.fixture
def yesterday():
    return (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def two_days_ago():
    return (date.today() - timedelta(days=2)).isoformat()
