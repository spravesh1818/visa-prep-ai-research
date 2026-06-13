"""Resolve local time-of-day context for consular-window greetings."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def interview_time_context(
    timezone: str, *, now: datetime | None = None
) -> dict[str, str]:
    """Return greeting context for the interview window's local time."""

    tz = ZoneInfo(timezone)
    local = (now or datetime.now(tz=ZoneInfo("UTC"))).astimezone(tz)
    hour = local.hour

    if 5 <= hour < 12:
        time_of_day = "morning"
        greeting_hint = "Good morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
        greeting_hint = "Good afternoon"
    elif 17 <= hour < 22:
        time_of_day = "evening"
        greeting_hint = "Good evening"
    else:
        time_of_day = "night"
        greeting_hint = "Hello"

    return {
        "timezone": timezone,
        "local_time": local.strftime("%H:%M"),
        "local_date": local.strftime("%A, %d %B %Y"),
        "time_of_day": time_of_day,
        "greeting_hint": greeting_hint,
    }
