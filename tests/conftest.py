"""Test setup: use a throwaway SQLite DB so tests never touch dev data."""

import os
import tempfile

# Must be set before app modules import settings.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["DEBUG"] = "false"
os.environ["ADMIN_TOKEN"] = "test-token"  # enables /api/trigger/* in tests


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists(_db_path):
        os.remove(_db_path)
