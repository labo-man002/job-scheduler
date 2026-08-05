
from enum import Enum


class AllocationStatus(Enum):
 
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"	
    RELEASED = "RELEASED"
    FAILED = "FAILED"