<<<<<<< HEAD
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
=======
from enum import Enum


class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
>>>>>>> 34ff04a (Align database models with ERD design)
