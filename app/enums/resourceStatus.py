from enum import Enum


class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
