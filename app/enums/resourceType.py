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
