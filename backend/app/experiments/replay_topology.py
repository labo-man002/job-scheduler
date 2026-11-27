"""Adapt the compact replay fabric to the placement domain."""

from collections import Counter

from app.domain.leaf_spine import (
    DeviceKind,
    EndpointRef,
    LeafSpineTopology,
    PortGroupConfig,
    Switch,
    SwitchHardwareConfig,
    SwitchRole,
)
from app.models import Node

from .replay_input import LeafSpineTopologyInput

LINK_CAPACITY_GBPS = 100
LINK_LATENCY_US = 1


def make_leaf_spine(config: LeafSpineTopologyInput, nodes: list[Node]) -> LeafSpineTopology:
    topology = LeafSpineTopology()
    leaf_ports = Counter(link.leaf for link in (*config.uplinks, *config.attachments))
    spine_ports = Counter(link.spine for link in config.uplinks)

    for role, ids, ports in (
        (SwitchRole.LEAF, config.leaves, leaf_ports),
        (SwitchRole.SPINE, spine_ports, spine_ports),
    ):
        for switch_id in sorted(ids):
            hardware = SwitchHardwareConfig(
                "replay-switch", (PortGroupConfig(max(1, ports[switch_id]), LINK_CAPACITY_GBPS),)
            )
            topology.add_switch(Switch(f"{role.value.lower()}-{switch_id}", role, hardware))

    for node in nodes:
        topology.add_node(node)

    used_ports: Counter[str] = Counter()

    def switch_port(switch_id: str) -> EndpointRef:
        used_ports[switch_id] += 1
        return EndpointRef(DeviceKind.SWITCH, switch_id, f"p{used_ports[switch_id]}")

    for link in sorted(config.attachments, key=lambda link: link.node):
        topology.add_link(
            EndpointRef(DeviceKind.NODE, str(link.node), "nic0"),
            switch_port(f"leaf-{link.leaf}"),
            capacity_gbps=LINK_CAPACITY_GBPS,
            latency_us=LINK_LATENCY_US,
        )
    for link in sorted(config.uplinks, key=lambda link: (link.leaf, link.spine)):
        topology.add_link(
            switch_port(f"leaf-{link.leaf}"),
            switch_port(f"spine-{link.spine}"),
            capacity_gbps=LINK_CAPACITY_GBPS,
            latency_us=LINK_LATENCY_US,
        )

    return topology
