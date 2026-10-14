"""Immutable runtime device snapshots; a switch generates and owns its ports."""

from dataclasses import dataclass, field, replace

from .hardware import SwitchHardwareConfig, _positive_speed
from .types import OperationalState, SwitchRole


def _validate_state(state):
    if not isinstance(state, OperationalState):
        raise ValueError("state must be an OperationalState")


@dataclass(frozen=True, slots=True)
class Port:
    number: int
    capacity_gbps: float
    state: OperationalState = OperationalState.UP


@dataclass(frozen=True, slots=True)
class Switch:
    id: str
    role: SwitchRole
    config: SwitchHardwareConfig
    state: OperationalState = OperationalState.UP
    _ports: tuple[Port, ...] = field(default=(), repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("switch id must be nonempty")
        if not isinstance(self.role, SwitchRole) or not isinstance(self.config, SwitchHardwareConfig):
            raise ValueError("switch requires a role and SwitchHardwareConfig")
        _validate_state(self.state)
        speeds = self.config.port_speeds()
        if not self._ports:
            object.__setattr__(self, "_ports", tuple(Port(i, speed) for i, speed in enumerate(speeds, 1)))
        elif len(self._ports) != len(speeds) or any(
            port.number != index or port.capacity_gbps != speeds[index - 1] or not isinstance(port.state, OperationalState)
            for index, port in enumerate(self._ports, 1)
        ):
            raise ValueError("port snapshots must match hardware config")

    def get_port(self, number: int) -> Port:
        if type(number) is not int or not 1 <= number <= len(self._ports):
            raise ValueError(f"switch {self.id} has no port {number}")
        return self._ports[number - 1]

    def ports(self) -> tuple[Port, ...]:
        return self._ports

    def with_port_state(self, number: int, state: OperationalState) -> "Switch":
        _validate_state(state)
        port = self.get_port(number)
        ports = list(self._ports)
        ports[number - 1] = replace(port, state=state)
        return replace(self, _ports=tuple(ports))


@dataclass(frozen=True, slots=True)
class NetworkInterface:
    id: str
    capacity_gbps: float
    state: OperationalState = OperationalState.UP


@dataclass(frozen=True, slots=True)
class GpuServer:
    id: str
    node_id: int
    nic_capacity_gbps: float
    state: OperationalState = OperationalState.UP
    nic_state: OperationalState = OperationalState.UP

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("server id must be nonempty")
        if type(self.node_id) is not int or self.node_id < 0:
            raise ValueError("server node_id must be a nonnegative integer")
        if not _positive_speed(self.nic_capacity_gbps):
            raise ValueError("NIC capacity must be finite and positive")
        _validate_state(self.state)
        _validate_state(self.nic_state)

    @property
    def nic(self) -> NetworkInterface:
        return NetworkInterface("nic0", self.nic_capacity_gbps, self.nic_state)
