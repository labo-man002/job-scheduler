<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class AllocationStatus(BasicEnum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
=======

from enum import Enum


class AllocationStatus(Enum):
 
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"	
    RELEASED = "RELEASED"
    FAILED = "FAILED"
>>>>>>> 1d3c52a (Start coding)
