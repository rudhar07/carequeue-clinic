"""The clinic's notion of "now".

Routes receive the clock as a FastAPI dependency so tests can pin it to a fixed
moment (booking rules depend on the current date and time).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def clinic_now() -> datetime:
    """Current wall-clock time in the clinic's timezone (naive, local)."""
    tz = ZoneInfo(get_settings().clinic_timezone)
    return datetime.now(tz).replace(tzinfo=None)
