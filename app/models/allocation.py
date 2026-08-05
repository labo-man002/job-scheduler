<<<<<<< HEAD
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.AllocationStatus import AllocationStatus

=======
from ctypes import Array

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func

from app.database import Base
from app.enums import AllocationStatus
>>>>>>> 1d3c52a (Start coding)

class Allocation(Base):
    __tablename__ = "allocation"

<<<<<<< HEAD
    allocation_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)
    begin_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    duration = Column(Integer, nullable=False)
    allocation_status = Column(
        Enum(AllocationStatus, name="allocation_status"),
        nullable=False,
        default=AllocationStatus.PENDING,
    )

    job = relationship("Job")
    allocation_nodes = relationship("AllocationNode", back_populates="allocation")
=======
    id = Column(Integer ,primary_key=True)
    job_id = Column(ForeignKey("job.id") ,nullable=False)
    begin_time =Column(DateTime, nullable=False, server_default=func.now())
    allocation_status = Column(Enum(AllocationStatus),default=AllocationStatus.PENDING)
    duration = Column(Integer ,nullable=False)
>>>>>>> 1d3c52a (Start coding)
