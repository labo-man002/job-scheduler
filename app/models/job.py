from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func

from app.database import Base
from app.enums.jobStatus import JobStatus
from app.enums.priority import Priority


class Job(Base):
    __tablename__ = "job"

    job_id = Column(Integer, primary_key=True)
    status = Column(
        Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.PENDING
    )
    priority = Column(
        Enum(Priority, name="priority"), nullable=False, default=Priority.NORMAL
    )
    duration = Column(Integer, nullable=False)
    client_id = Column(Integer, ForeignKey("client.client_id"), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


