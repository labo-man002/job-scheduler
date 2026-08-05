from ctypes import Array

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.database import Base
from app.enums import AllocationStatus

class Allocation(Base):
    __tablename__ = "allocation"

    id = Column(Integer ,primary_key=True)
    job_id = Column(ForeignKey("job.id") ,nullable=False)
    begin_time =Column(DateTime, nullable=False, server_default=func.now())
    allocation_status = Column(Enum(AllocationStatus),default=AllocationStatus.PENDING)
    duration = Column(Integer ,nullable=False)