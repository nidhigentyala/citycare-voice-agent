"""SQLAlchemy models for CityCare Clinic."""
from sqlalchemy import Column, Integer, String
from backend.database import Base


class AppointmentDB(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)
    time = Column(String(5), nullable=False)
    service = Column(String(200), nullable=False)
    # Nullable to preserve existing rows while calendar integration is rolled out.
    google_calendar_event_id = Column(String(255), nullable=True, index=True)
