"""Small shared helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (matches the naive DateTime columns we store)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
