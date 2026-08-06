from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.database import Base
from app.enums.eventType import EventType


class JobEvent(Base):
    __tablename__ = "job_event"

    id = Column(Integer, primary_key=True)
    event_type_id = Column(Enum(EventType, name="event_type"), nullable=False)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    comment = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)
