from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
<<<<<<< HEAD
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.jobStatus import JobStatus
=======

from app.database import Base
from app.enums.eventType import EventType
>>>>>>> 34ff04a (Align database models with ERD design)


class JobEvent(Base):
    __tablename__ = "job_event"

    id = Column(Integer, primary_key=True)
<<<<<<< HEAD
    event_type = Column(Enum(JobStatus, name="event_type"), nullable=False)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    comment = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)

    job = relationship("Job", back_populates="events")
=======
    event_type_id = Column(Enum(EventType, name="event_type"), nullable=False)
    time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    comment = Column(String, nullable=False)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)
>>>>>>> 34ff04a (Align database models with ERD design)
