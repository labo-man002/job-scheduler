<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class JobStatus(BasicEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
=======

from enum import Enum


class JobStatus(Enum):
  Pending ="Pending"
  Queued = "Queued"
  Running = "Running"
  Completed = "Completed"
  Cunceled = "Cunceled"
  Failed = "Failed"
  
>>>>>>> 1d3c52a (Start coding)
