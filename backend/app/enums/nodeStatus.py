from app.enums.basicEnum import BasicEnum


class NodeStatus(BasicEnum):
    IDLE = "IDLE"
    ALLOCATED = "ALLOCATED"
    MIXED = "MIXED"
    DOWN = "DOWN"
