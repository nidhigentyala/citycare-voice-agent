"""Google Calendar integration for CityCare Clinic appointments."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    """Authenticate with the configured Google service account."""
    credentials_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not credentials_file:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is missing from .env.local")

    credentials_path = Path(credentials_file).expanduser()
    if not credentials_path.is_absolute():
        credentials_path = PROJECT_ROOT / credentials_path
    if not credentials_path.is_file():
        raise FileNotFoundError(f"Service account JSON not found: {credentials_path}")

    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path), scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_calendar_id() -> str:
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
    if not calendar_id:
        raise ValueError("GOOGLE_CALENDAR_ID is missing from .env.local")
    return calendar_id


def get_calendar_timezone() -> str:
    return os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata")


def test_calendar_access():
    """Return metadata for the configured calendar."""
    calendar = get_calendar_service().calendars().get(
        calendarId=get_calendar_id()
    ).execute()
    return {
        "calendar_name": calendar.get("summary"),
        "calendar_id": calendar.get("id"),
        "timezone": calendar.get("timeZone", get_calendar_timezone()),
    }


def list_calendar_events(start: datetime, end: datetime):
    """List events overlapping the supplied aware datetime interval."""
    tz = ZoneInfo(get_calendar_timezone())
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)

    result = get_calendar_service().events().list(
        calendarId=get_calendar_id(),
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute()
    return result.get("items", [])


def is_calendar_slot_available(start: datetime, duration_minutes: int = 30,
                               exclude_event_id: str | None = None) -> bool:
    """Return False if an existing Google Calendar event overlaps the requested slot."""
    tz = ZoneInfo(get_calendar_timezone())
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    end = start + timedelta(minutes=duration_minutes)

    for event in list_calendar_events(start, end):
        if exclude_event_id and event.get("id") == exclude_event_id:
            continue
        if event.get("status") == "cancelled" or event.get("transparency") == "transparent":
            continue
        event_start = event.get("start", {}).get("dateTime")
        event_end = event.get("end", {}).get("dateTime")
        # All-day events are treated as unavailable for that day.
        if not event_start or not event_end:
            return False
        existing_start = datetime.fromisoformat(event_start.replace("Z", "+00:00"))
        existing_end = datetime.fromisoformat(event_end.replace("Z", "+00:00"))
        if start < existing_end and end > existing_start:
            return False
    return True


def create_appointment_event(*, name: str, phone: str, service_name: str,
                             start: datetime, duration_minutes: int = 30) -> dict:
    """Create an appointment event and return the Google event resource."""
    tz_name = get_calendar_timezone()
    tz = ZoneInfo(tz_name)
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    end = start + timedelta(minutes=duration_minutes)

    if not is_calendar_slot_available(start, duration_minutes):
        raise ValueError("The requested appointment time conflicts with a Google Calendar event.")

    event = {
        "summary": f"CityCare Clinic - {service_name}",
        "description": (
            f"Patient: {name}\n"
            f"Phone: {phone}\n"
            f"Service: {service_name}\n"
            "Created by the CityCare Clinic appointment system."
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
    }
    return get_calendar_service().events().insert(
        calendarId=get_calendar_id(), body=event
    ).execute()


def update_appointment_event(event_id: str, *, name: str, phone: str,
                             service_name: str, start: datetime,
                             duration_minutes: int = 30) -> dict:
    """Update an existing Google Calendar event."""
    tz_name = get_calendar_timezone()
    tz = ZoneInfo(tz_name)
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    end = start + timedelta(minutes=duration_minutes)

    if not is_calendar_slot_available(start, duration_minutes, exclude_event_id=event_id):
        raise ValueError("The requested appointment time conflicts with a Google Calendar event.")

    service = get_calendar_service()
    current = service.events().get(calendarId=get_calendar_id(), eventId=event_id).execute()
    current.update({
        "summary": f"CityCare Clinic - {service_name}",
        "description": (
            f"Patient: {name}\nPhone: {phone}\nService: {service_name}\n"
            "Updated by the CityCare Clinic appointment system."
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
    })
    return service.events().update(
        calendarId=get_calendar_id(), eventId=event_id, body=current
    ).execute()


def delete_appointment_event(event_id: str) -> None:
    """Delete a previously created Google Calendar event."""
    get_calendar_service().events().delete(
        calendarId=get_calendar_id(), eventId=event_id
    ).execute()
