from enum import Enum


class ClientStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
