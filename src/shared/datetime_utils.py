"""Timezone-aware datetime utilities.

This module provides consistent timezone handling across the application.
All datetime values should use UTC timezone for storage and comparison.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Get current datetime with UTC timezone.

    This replaces datetime.utcnow() which returns naive datetime.
    Always use this function instead of datetime.utcnow() or datetime.now().

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone.

    If datetime is naive (no timezone), assumes UTC and adds it.
    If datetime has different timezone, converts to UTC.

    Args:
        dt: Datetime to ensure is UTC

    Returns:
        Datetime with UTC timezone, or None if input is None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC and add timezone
        return dt.replace(tzinfo=timezone.utc)

    # Convert to UTC if different timezone
    return dt.astimezone(timezone.utc)


def is_expired(expiry: datetime | None, now: datetime | None = None) -> bool:
    """Check if a datetime has expired.

    Args:
        expiry: Expiration datetime to check
        now: Current datetime for comparison (defaults to utc_now())

    Returns:
        True if expired (expiry is in the past), False otherwise
    """
    if expiry is None:
        return False

    if now is None:
        now = utc_now()

    # Ensure both have timezone info for comparison
    expiry = ensure_utc(expiry)
    now = ensure_utc(now)

    return expiry < now


def datetime_to_iso(dt: datetime | None) -> str | None:
    """Convert datetime to ISO 8601 string.

    Args:
        dt: Datetime to convert

    Returns:
        ISO 8601 formatted string, or None if input is None
    """
    if dt is None:
        return None
    return ensure_utc(dt).isoformat()


def iso_to_datetime(iso_string: str | None) -> datetime | None:
    """Parse ISO 8601 string to datetime.

    Args:
        iso_string: ISO 8601 formatted string

    Returns:
        Datetime with UTC timezone, or None if input is None
    """
    if iso_string is None:
        return None

    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return ensure_utc(dt)
