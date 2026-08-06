<<<<<<< HEAD
<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class AllocationStatus(BasicEnum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
=======

=======
>>>>>>> 34ff04a (Align database models with ERD design)
from enum import Enum


class AllocationStatus(str, Enum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
<<<<<<< HEAD
>>>>>>> 1d3c52a (Start coding)
=======
>>>>>>> 34ff04a (Align database models with ERD design)
