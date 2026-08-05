<<<<<<< HEAD
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.jobStatus import JobStatus
=======

from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
>>>>>>> 1d3c52a (Start coding)
from app.enums.priority import Priority


class Job(Base):
    __tablename__ = "job"

<<<<<<< HEAD
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

    requirements = relationship("ResourceRequirement")
    client = relationship("Client", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job")


=======
    id = Column(Integer ,primary_key=True)
    client_id = Column(Integer ,ForeignKey("client.id"),nullable=False)
    priority_status = Column(Enum(Priority) ,nullable=False ,default=Priority.Normal)
    duration = Column(Integer ,nullable=False)
>>>>>>> 1d3c52a (Start coding)
