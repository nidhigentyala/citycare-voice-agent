"""Create a temporary test event in the configured CityCare Google Calendar.

Run from day5/:
    uv run --active python test_google_calendar_event.py

This creates a real event. Delete it from Google Calendar after verifying it.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.google_calendar import (
    create_appointment_event,
    get_calendar_timezone,
    test_calendar_access,
)

timezone = ZoneInfo(get_calendar_timezone())
now = datetime.now(timezone)
start = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

# Avoid choosing a time that has already passed because of timezone/date edge cases.
if start <= now:
    start += timedelta(days=1)

print("Calendar:", test_calendar_access())
print("Creating a 30-minute test event at:", start.isoformat())

event = create_appointment_event(
    name="CityCare Calendar Test",
    phone="TEST-DO-NOT-CALL",
    service_name="Calendar Integration Test",
    start=start,
    duration_minutes=30,
)
print("Event created successfully.")
print("Event ID:", event.get("id"))
print("Event link:", event.get("htmlLink"))
print("Start:", event.get("start"))
print("End:", event.get("end"))
