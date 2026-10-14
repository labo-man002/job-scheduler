"""Code-defined, immutable switch hardware capabilities (Gbps)."""

from dataclasses import dataclass
from math import isfinite


def _positive_speed(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0


@dataclass(frozen=True, slots=True)
class PortGroupConfig:
    count: int
    speed_gbps: float

    def __post_init__(self):
        if type(self.count) is not int or self.count <= 0:
            raise ValueError("port group count must be a positive integer")
        if not _positive_speed(self.speed_gbps):
            raise ValueError("port group speed_gbps must be finite and positive")


@dataclass(frozen=True, slots=True)
class SwitchHardwareConfig:
    model: str
    port_groups: tuple[PortGroupConfig, ...]

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("hardware model name must be nonempty")
        groups = tuple(self.port_groups)
        if not groups or any(not isinstance(group, PortGroupConfig) for group in groups):
            raise ValueError("at least one valid port group is required")
        object.__setattr__(self, "port_groups", groups)

    @property
    def port_count(self) -> int:
        return sum(group.count for group in self.port_groups)

    def port_speeds(self) -> tuple[float, ...]:
        return tuple(group.speed_gbps for group in self.port_groups for _ in range(group.count))


# Illustrative, not a vendor hardware claim.
DEMO_4X400 = SwitchHardwareConfig("demo-4x400", (PortGroupConfig(4, 400.0),))
