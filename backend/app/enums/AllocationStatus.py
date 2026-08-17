from app.enums.basicEnum import BasicEnum


class AllocationStatus(BasicEnum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    FAILED = "FAILED"
