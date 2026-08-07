from enum import Enum


class NodeStatus(str, Enum):
    IDLE = "IDLE"
    ALLOCATED = "ALLOCATED"
    MIXED = "MIXED"
    DOWN = "DOWN"
