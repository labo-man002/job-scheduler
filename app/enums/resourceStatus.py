<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class ResourceStatus(BasicEnum):
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
=======



from enum import Enum


class ResourceStatus(Enum):
    AVAILABLE = "AVAILABLE"	
    ALLOCATED ="AVAILABLE"	
    UNAVAILABLE	="AVAILABLE"
    FAILED	="AVAILABLE"
>>>>>>> 1d3c52a (Start coding)
