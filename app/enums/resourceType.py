from enum import Enum


class ResourceType(str, Enum):
    CPU = "CPU"
    GPU = "GPU"
    MEM = "MEM"
