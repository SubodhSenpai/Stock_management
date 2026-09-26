"""Time helpers.

Schedule dates and "is it late" comparisons are plain calendar dates, but they are derived
from an explicit UTC clock so a result never depends on the server's local timezone.
"""

from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return utcnow().date()
