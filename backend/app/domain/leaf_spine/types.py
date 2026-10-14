"""Immutable IDs, enums and domain-specific errors for a two-tier network fabric."""

from dataclasses import dataclass
from enum import Enum


class DeviceKind(str, Enum):
    SWITCH = "SWITCH"
    GPU_SERVER = "GPU_SERVER"


class SwitchRole(str, Enum):
    LEAF = "LEAF"
    SPINE = "SPINE"


class LinkKind(str, Enum):
    LEAF_SPINE = "LEAF_SPINE"
    SERVER_LEAF = "SERVER_LEAF"


class OperationalState(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass(frozen=True, slots=True)
class DeviceRef:
    kind: DeviceKind
    device_id: str

    def __post_init__(self):
        if not isinstance(self.kind, DeviceKind) or not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValueError("DeviceRef requires a kind and a nonempty device_id")


@dataclass(frozen=True, slots=True)
class EndpointRef:
    device_kind: DeviceKind
    device_id: str
    endpoint_id: str

    def __post_init__(self):
        if not isinstance(self.device_kind, DeviceKind):
            raise ValueError("EndpointRef requires a valid device kind")
        if any(not isinstance(value, str) or not value.strip() for value in (self.device_id, self.endpoint_id)):
            raise ValueError("EndpointRef requires nonempty device_id and endpoint_id")

    @property
    def device(self) -> DeviceRef:
        return DeviceRef(self.device_kind, self.device_id)


class LeafSpineError(ValueError):
    """Base class for fabric domain validation failures."""


class DuplicateIdError(LeafSpineError):
    pass


class UnknownDeviceError(LeafSpineError):
    pass


class UnknownEndpointError(LeafSpineError):
    pass


class UnknownLinkError(LeafSpineError):
    pass


class EndpointOccupiedError(LeafSpineError):
    pass


class InvalidConnectionError(LeafSpineError):
    pass


class InvalidLinkPropertiesError(LeafSpineError):
    pass


class DeviceInUseError(LeafSpineError):
    pass


class InconsistentInventoryError(LeafSpineError):
    pass
