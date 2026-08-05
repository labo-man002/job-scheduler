
from enum import Enum


class JobStatus(Enum):
  Pending ="Pending"
  Queued = "Queued"
  Running = "Running"
  Completed = "Completed"
  Cunceled = "Cunceled"
  Failed = "Failed"
  