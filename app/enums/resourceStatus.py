from app.enums.basicEnum import BasicEnum


class ResourceStatus(BasicEnum):
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
