"""FastAPI backend for CityCare Clinic."""
import asyncio
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local")

from backend.database import Base, SessionLocal, engine
from backend.google_calendar import (
    create_appointment_event,
    delete_appointment_event,
    get_calendar_timezone,
    is_calendar_slot_available,
    test_calendar_access,
    update_appointment_event,
)
from backend.models import AppointmentDB

app = FastAPI(
    title="CityCare Clinic Backend",
    description="FastAPI backend for the CityCare clinic voice agent",
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]
APPOINTMENT_DURATION_MINUTES = 30


class AppointmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=1, max_length=30)
    date: str
    time: str
    service: str = Field(min_length=1, max_length=200)


class AppointmentUpdate(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None


@app.on_event("startup")
def initialize_database():
    """Create tables and add the calendar event ID column to existing installations."""
    Base.metadata.create_all(bind=engine)
    # create_all() does not add columns to an existing table.
    inspector = inspect(engine)
    if "appointments" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("appointments")}
        if "google_calendar_event_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text(
                    "ALTER TABLE appointments ADD COLUMN google_calendar_event_id VARCHAR(255)"
                ))
    print("Database tables initialized successfully.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start_time = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - start_time) * 1000
    print(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.2f} ms)")
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


def validate_date(date_string: str) -> date:
    try:
        parsed = date.fromisoformat(date_string)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    if parsed < date.today():
        raise HTTPException(status_code=400, detail="Appointment date cannot be in the past.")
    return parsed


def validate_time(time_string: str) -> datetime:
    try:
        return datetime.strptime(time_string, "%H:%M")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM (24-hour time).")


def appointment_start(date_string: str, time_string: str) -> datetime:
    timezone = ZoneInfo(get_calendar_timezone())
    return datetime.combine(date.fromisoformat(date_string), datetime.strptime(time_string, "%H:%M").time()).replace(tzinfo=timezone)


def appointment_to_dict(appointment: AppointmentDB) -> dict:
    return {
        "id": appointment.id,
        "name": appointment.name,
        "phone": appointment.phone,
        "date": appointment.date,
        "time": appointment.time,
        "service": appointment.service,
        "google_calendar_event_id": appointment.google_calendar_event_id,
    }


def get_available_slots(target_date: str, db: Session, exclude_appointment_id: Optional[int] = None):
    query = db.query(AppointmentDB).filter(AppointmentDB.date == target_date)
    if exclude_appointment_id is not None:
        query = query.filter(AppointmentDB.id != exclude_appointment_id)
    booked_times = {appointment.time for appointment in query.all()}
    available = []
    for slot in DEFAULT_SLOTS:
        if slot in booked_times:
            continue
        try:
            start = appointment_start(target_date, slot)
            if is_calendar_slot_available(start, APPOINTMENT_DURATION_MINUTES):
                available.append(slot)
        except Exception as exc:
            # Fail closed: do not advertise availability if Google Calendar cannot be checked.
            print(f"Google Calendar availability check failed for {target_date} {slot}: {exc}")
            continue
    return available


@app.get("/")
def root():
    return {"message": "CityCare Clinic backend is running"}


@app.get("/health/database")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "connected", "database": "PostgreSQL"}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database connection failed.")


@app.get("/health/calendar")
def calendar_health():
    try:
        return {"status": "connected", **test_calendar_access()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Google Calendar connection failed: {exc}")


@app.get("/slots")
def list_slots(date: str = Query(...), db: Session = Depends(get_db)):
    validate_date(date)
    try:
        return {"date": date, "available_slots": get_available_slots(date, db)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not check appointment availability: {exc}")


@app.post("/appointments")
def book_appointment(appointment: AppointmentCreate, db: Session = Depends(get_db)):
    validate_date(appointment.date)
    validate_time(appointment.time)
    for value, label in ((appointment.name, "Patient name"), (appointment.phone, "Phone number"), (appointment.service, "Appointment service")):
        if not value.strip():
            raise HTTPException(status_code=400, detail=f"{label} cannot be empty.")

    available_slots = get_available_slots(appointment.date, db)
    if appointment.time not in available_slots:
        raise HTTPException(status_code=409, detail="The requested appointment time is not available.")

    event = None
    try:
        event = create_appointment_event(
            name=appointment.name.strip(),
            phone=appointment.phone.strip(),
            service_name=appointment.service.strip(),
            start=appointment_start(appointment.date, appointment.time),
            duration_minutes=APPOINTMENT_DURATION_MINUTES,
        )
        new_appointment = AppointmentDB(
            name=appointment.name.strip(),
            phone=appointment.phone.strip(),
            date=appointment.date,
            time=appointment.time,
            service=appointment.service.strip(),
            google_calendar_event_id=event.get("id"),
        )
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        db.rollback()
        # If the event was created but the database save failed, remove the orphan event.
        if event and event.get("id"):
            try:
                delete_appointment_event(event["id"])
            except Exception as cleanup_exc:
                print(f"Warning: could not remove orphan Google Calendar event: {cleanup_exc}")
        print(f"Appointment booking failed: {exc}")
        raise HTTPException(status_code=500, detail="Unable to book appointment in the database and Google Calendar.")
    return {"message": "Appointment booked successfully", "appointment": appointment_to_dict(new_appointment)}


@app.get("/appointments/all")
def get_all_appointments(db: Session = Depends(get_db)):
    appointments = db.query(AppointmentDB).order_by(AppointmentDB.id).all()
    return [appointment_to_dict(item) for item in appointments]


@app.patch("/appointments/{appointment_id}")
def change_appointment(appointment_id: int, update: AppointmentUpdate, db: Session = Depends(get_db)):
    appointment = db.get(AppointmentDB, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    new_date = update.date if update.date is not None else appointment.date
    new_time = update.time if update.time is not None else appointment.time
    validate_date(new_date)
    validate_time(new_time)

    if new_date != appointment.date or new_time != appointment.time:
        available_slots = get_available_slots(new_date, db, exclude_appointment_id=appointment_id)
        if new_time not in available_slots:
            raise HTTPException(status_code=409, detail="The requested new appointment time is not available.")

    old_date, old_time = appointment.date, appointment.time
    old_event_id = appointment.google_calendar_event_id
    try:
        if old_event_id:
            update_appointment_event(
                old_event_id,
                name=appointment.name,
                phone=appointment.phone,
                service_name=appointment.service,
                start=appointment_start(new_date, new_time),
                duration_minutes=APPOINTMENT_DURATION_MINUTES,
            )
        else:
            event = create_appointment_event(
                name=appointment.name,
                phone=appointment.phone,
                service_name=appointment.service,
                start=appointment_start(new_date, new_time),
                duration_minutes=APPOINTMENT_DURATION_MINUTES,
            )
            appointment.google_calendar_event_id = event.get("id")
        appointment.date = new_date
        appointment.time = new_time
        db.commit()
        db.refresh(appointment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        db.rollback()
        print(f"Appointment update failed: {exc}")
        raise HTTPException(status_code=500, detail="Unable to update the appointment in Google Calendar and the database.")
    return {"message": "Appointment updated successfully", "appointment": appointment_to_dict(appointment)}


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.get(AppointmentDB, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    cancelled = appointment_to_dict(appointment)
    try:
        if appointment.google_calendar_event_id:
            delete_appointment_event(appointment.google_calendar_event_id)
        db.delete(appointment)
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"Appointment cancellation failed: {exc}")
        raise HTTPException(status_code=500, detail="Unable to cancel the appointment.")
    return {"message": "Appointment cancelled successfully", "appointment": cancelled}


@app.get("/appointments")
def find_appointments(phone: str = Query(...), db: Session = Depends(get_db)):
    results = db.query(AppointmentDB).filter(AppointmentDB.phone == phone).order_by(AppointmentDB.id).all()
    return {"appointments": [appointment_to_dict(item) for item in results]}


@app.get("/slow")
async def slow_endpoint():
    await asyncio.sleep(3)
    return {"message": "Slow endpoint completed"}


@app.get("/broken")
async def broken_endpoint():
    raise HTTPException(status_code=500, detail="Booking backend is temporarily unavailable.")


@app.get("/bills")
async def get_bill(phone: str):
    return {"phone": phone, "bill_amount": 2450.00, "due_date": "2026-10-15"}


@app.get("/token", tags=["LiveKit"])
async def get_token(room: str):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(status_code=500, detail="LiveKit credentials are not configured")
    if not room.strip() or len(room) > 100:
        raise HTTPException(status_code=400, detail="Invalid room")

    identity = f"guest-{uuid4().hex[:12]}"
    room_config = api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name="citycare")])
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(room_config)
        .to_jwt()
    )
    return {"token": token, "url": livekit_url, "room": room, "identity": identity}
