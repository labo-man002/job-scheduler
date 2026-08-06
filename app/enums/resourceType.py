<<<<<<< HEAD
<<<<<<< HEAD
from app.enums.basicEnum import BasicEnum


class ResourceType(BasicEnum):
    CPU = "CPU"
    GPU = "GPU"
    MEM = "MEM"
=======


from enum import Enum


class ResourceType(Enum):
    CPU	="CPU"
    GPU	="GPU"
    MEM = "MEM"	
>>>>>>> 1d3c52a (Start coding)
=======
from enum import Enum


class ResourceType(str, Enum):
    CPU = "CPU"
    GPU = "GPU"
    MEM = "MEM"
>>>>>>> 34ff04a (Align database models with ERD design)
