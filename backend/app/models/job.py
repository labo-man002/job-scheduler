from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

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
    min_nodes = Column(Integer, nullable=False, default=1)
    max_nodes = Column(Integer, nullable=True)
    require_full_connectivity = Column(Boolean, nullable=False, default=False)
    min_bandwidth_gbps = Column(Float, nullable=True)
    max_latency_us = Column(Float, nullable=True)
    client_id = Column(Integer, ForeignKey("client.client_id"), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    requirements = relationship("ResourceRequirement")
    client = relationship("Client", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job")


