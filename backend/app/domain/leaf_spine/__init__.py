"""Leaf-Spine fabric model and its generic placement-topology adapter."""

from .devices import NetworkEndpoint, Port, Switch
from .gpu_candidates import GpuCandidate, GpuCandidateFinder
from .hardware import DEMO_4X400, PortGroupConfig, SwitchHardwareConfig
from .link import Link, NetworkPath
from .topology import LeafSpineTopology, LeafSpineTopologyView
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
    "InconsistentInventoryError",
    "InvalidConnectionError",
    "InvalidLinkPropertiesError",
    "LeafSpineError",
    "LeafSpineTopology",
    "LeafSpineTopologyView",
    "Link",
    "LinkKind",
    "NetworkEndpoint",
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
