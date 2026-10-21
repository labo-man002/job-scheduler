"""Standalone leaf/spine fabric model; intentionally not wired into Placer yet."""

from .devices import GpuServer, NetworkEndpoint, NetworkInterface, Port, Switch
from .gpu_candidates import GpuCandidate, GpuCandidateFinder
from .hardware import DEMO_4X400, PortGroupConfig, SwitchHardwareConfig
from .link import Link, NetworkPath
from .topology import LeafSpineTopology
from .types import (
    DeviceInUseError,
    DeviceKind,
    DeviceRef,
    DuplicateIdError,
    EndpointOccupiedError,
    EndpointRef,
    InconsistentInventoryError,
    InvalidConnectionError,
    InvalidLinkPropertiesError,
    LeafSpineError,
    LinkKind,
    OperationalState,
    SwitchRole,
    UnknownDeviceError,
    UnknownEndpointError,
    UnknownLinkError,
)

__all__ = [
    "DEMO_4X400",
    "DeviceInUseError",
    "DeviceKind",
    "DeviceRef",
    "DuplicateIdError",
    "EndpointOccupiedError",
    "EndpointRef",
    "GpuCandidate",
    "GpuCandidateFinder",
    "GpuServer",
    "InconsistentInventoryError",
    "InvalidConnectionError",
    "InvalidLinkPropertiesError",
    "LeafSpineError",
    "LeafSpineTopology",
    "Link",
    "LinkKind",
    "NetworkEndpoint",
    "NetworkInterface",
    "NetworkPath",
    "OperationalState",
    "Port",
    "PortGroupConfig",
    "Switch",
    "SwitchHardwareConfig",
    "SwitchRole",
    "UnknownDeviceError",
    "UnknownEndpointError",
    "UnknownLinkError",
]
