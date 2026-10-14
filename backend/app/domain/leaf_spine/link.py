"""Canonical immutable physical links and path snapshots."""

from dataclasses import dataclass
from math import isfinite

from .hardware import _positive_speed
from .types import DeviceRef, EndpointRef, LinkKind, OperationalState


@dataclass(frozen=True, slots=True)
class Link:
    id: str
    a: EndpointRef
    b: EndpointRef
    kind: LinkKind
    capacity_gbps: float
    latency_us: float
    state: OperationalState = OperationalState.UP

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("link ID must be nonempty")
        if self.a == self.b or not isinstance(self.a, EndpointRef) or not isinstance(self.b, EndpointRef):
            raise ValueError("link must connect distinct endpoints")
        if not isinstance(self.kind, LinkKind) or not isinstance(self.state, OperationalState):
            raise ValueError("link kind and state must be valid enums")
        if not _positive_speed(self.capacity_gbps):
            raise ValueError("link capacity must be positive and finite")
        if not isinstance(self.latency_us, (int, float)) or isinstance(self.latency_us, bool) or not isfinite(self.latency_us) or self.latency_us < 0:
            raise ValueError("latency must be nonnegative and finite")


@dataclass(frozen=True, slots=True)
class NetworkPath:
    devices: tuple[DeviceRef, ...]
    link_ids: tuple[str, ...]
    total_latency_us: float
    bottleneck_gbps: float
