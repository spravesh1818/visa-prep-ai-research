"""Tests for interview window local time context."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.interview.time_context import interview_time_context
from app.ontology.models import Ontology


def test_morning_london():
    ctx = interview_time_context(
        "Europe/London",
        now=datetime(2026, 6, 12, 8, 30, tzinfo=ZoneInfo("Europe/London")),
    )
    assert ctx["time_of_day"] == "morning"
    assert ctx["greeting_hint"] == "Good morning"
    assert ctx["local_time"] == "08:30"


def test_afternoon_london():
    ctx = interview_time_context(
        "Europe/London",
        now=datetime(2026, 6, 12, 15, 0, tzinfo=ZoneInfo("Europe/London")),
    )
    assert ctx["time_of_day"] == "afternoon"
    assert ctx["greeting_hint"] == "Good afternoon"


def test_evening_new_york():
    ctx = interview_time_context(
        "America/New_York",
        now=datetime(2026, 6, 12, 19, 0, tzinfo=ZoneInfo("America/New_York")),
    )
    assert ctx["time_of_day"] == "evening"
    assert ctx["greeting_hint"] == "Good evening"


def test_invalid_ontology_timezone_rejected():
    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        Ontology(
            country="US",
            visa_type="F1",
            display_name="Test",
            timezone="Not/A/Timezone",
            topics=[
                {
                    "id": "t1",
                    "label": "T",
                    "intent": "test",
                }
            ],
        )
