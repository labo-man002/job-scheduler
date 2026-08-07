from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func

from app.database import Base
from app.enums.AllocationStatus import AllocationStatus


class Allocation(Base):
    __tablename__ = "allocation"

    allocation_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)
    begin_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    duration = Column(Integer, nullable=False)
    allocation_status = Column(
        Enum(AllocationStatus, name="allocation_status"),
        nullable=False,
        default=AllocationStatus.PENDING,
    )
