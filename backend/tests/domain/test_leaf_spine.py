"""Contract tests for the standalone fabric aggregate (no DB required)."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from app.domain.leaf_spine import (
    DeviceKind, DeviceInUseError, DuplicateIdError, EndpointOccupiedError,
    EndpointRef, GpuServer, InvalidConnectionError, InvalidLinkPropertiesError,
    LeafSpineTopology, LinkKind, OperationalState, PortGroupConfig, Switch,
    SwitchHardwareConfig, SwitchRole, UnknownDeviceError, UnknownEndpointError,
    UnknownLinkError,
)


CONFIG = SwitchHardwareConfig("test", (PortGroupConfig(4, 400),))


def port(name, n):
    return EndpointRef(DeviceKind.SWITCH, name, f"p{n}")


def nic(name):
    return EndpointRef(DeviceKind.GPU_SERVER, name, "nic0")


def network():
    fabric = LeafSpineTopology()
    for switch_id, role in (
        ("leaf-A", SwitchRole.LEAF), ("leaf-B", SwitchRole.LEAF),
        ("spine-1", SwitchRole.SPINE), ("spine-2", SwitchRole.SPINE),
    ):
        fabric.add_switch(Switch(switch_id, role, CONFIG))
    fabric.add_server(GpuServer("gpu-A", 10, 100))
    fabric.add_server(GpuServer("gpu-B", 11, 100))
    for name, a, b, cap, latency in (
        ("L1", port("leaf-A", 1), port("spine-1", 1), 400, 2),
        ("L2", port("leaf-B", 1), port("spine-1", 2), 400, 2),
        ("L3", port("leaf-A", 2), port("spine-2", 1), 200, 3),
        ("L4", port("leaf-B", 2), port("spine-2", 2), 200, 3),
        ("L5", port("leaf-A", 3), nic("gpu-A"), 100, 1),
        ("L6", port("leaf-B", 3), nic("gpu-B"), 100, 1),
    ):
        fabric.add_link(a, b, capacity_gbps=cap, latency_us=latency, link_id=name)
    return fabric


def test_hardware_configs_are_frozen_and_switch_ports_are_independent():
    mixed = SwitchHardwareConfig("mixed", (PortGroupConfig(2, 400), PortGroupConfig(1, 100)))
    a = Switch("a", SwitchRole.LEAF, mixed)
    b = Switch("b", SwitchRole.SPINE, mixed)
    assert [(p.number, p.capacity_gbps) for p in a.ports()] == [(1, 400), (2, 400), (3, 100)]
    assert a.ports() is a.ports()
    with pytest.raises(FrozenInstanceError):
        mixed.model = "mutated"
    with pytest.raises(FrozenInstanceError):
        a.ports()[0].state = OperationalState.DOWN
    assert b.get_port(1).state == OperationalState.UP
    with pytest.raises(ValueError):
        a.get_port(4)


@pytest.mark.parametrize("speed", [0, -1, inf, nan, True])
def test_rejects_invalid_port_speeds(speed):
    with pytest.raises(ValueError):
        PortGroupConfig(1, speed)


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_rejects_invalid_port_counts(count):
    with pytest.raises(ValueError):
        PortGroupConfig(count, 100)


def test_rejects_bad_hardware_or_server():
    with pytest.raises(ValueError):
        SwitchHardwareConfig("", (PortGroupConfig(1, 100),))
    with pytest.raises(ValueError):
        SwitchHardwareConfig("empty", ())
    with pytest.raises(ValueError):
        GpuServer("gpu", 4, 0)
    with pytest.raises(ValueError):
        GpuServer("gpu", -1, 100)


def test_bidirectional_allowed_pairs_and_inferred_kinds():
    for reversed_order in (False, True):
        fabric = LeafSpineTopology()
        fabric.add_switch(Switch("leaf", SwitchRole.LEAF, CONFIG))
        fabric.add_switch(Switch("spine", SwitchRole.SPINE, CONFIG))
        fabric.add_server(GpuServer("gpu", 4, 100))
        ends = (port("leaf", 1), port("spine", 1))
        a, b = ends[::-1] if reversed_order else ends
        assert fabric.add_link(a, b, capacity_gbps=400, latency_us=1).kind == LinkKind.LEAF_SPINE
        ends = (port("leaf", 2), nic("gpu"))
        a, b = ends[::-1] if reversed_order else ends
        assert fabric.add_link(a, b, capacity_gbps=100, latency_us=0).kind == LinkKind.SERVER_LEAF
        fabric._assert_indexes_consistent()


@pytest.mark.parametrize("a,b", [
    (port("leaf-A", 1), port("leaf-B", 1)),
    (port("spine-1", 1), port("spine-2", 1)),
    (nic("gpu-A"), nic("gpu-B")),
    (nic("gpu-A"), port("spine-1", 1)),
    (port("leaf-A", 1), port("leaf-A", 1)),
])
def test_illegal_pairs_rejected_without_side_effects(a, b):
    fabric = network()
    before = fabric.links()
    with pytest.raises((InvalidConnectionError, EndpointOccupiedError)):
        fabric.add_link(a, b, capacity_gbps=100, latency_us=1)
    assert fabric.links() == before
    fabric._assert_indexes_consistent()


def test_missing_occupied_duplicate_and_bad_properties_are_atomic():
    fabric = network()
    before = fabric.links()
    bad = [
        (port("missing", 1), port("spine-1", 3), 1, 1, None, UnknownEndpointError),
        (port("leaf-A", 20), port("spine-1", 3), 1, 1, None, UnknownEndpointError),
        (port("leaf-A", 4), port("spine-1", 3), 401, 1, None, InvalidLinkPropertiesError),
        (port("leaf-A", 4), port("spine-1", 3), 100, -1, None, InvalidLinkPropertiesError),
        (port("leaf-A", 4), port("spine-1", 3), nan, 1, None, InvalidLinkPropertiesError),
        (port("leaf-A", 4), port("spine-1", 3), 100, inf, None, InvalidLinkPropertiesError),
        (port("leaf-A", 4), port("spine-1", 3), 100, 1, "L1", DuplicateIdError),
        (port("leaf-A", 1), port("spine-1", 3), 100, 1, None, EndpointOccupiedError),
    ]
    for a, b, cap, latency, link_id, error in bad:
        with pytest.raises(error):
            fabric.add_link(a, b, capacity_gbps=cap, latency_us=latency, link_id=link_id)
        assert fabric.links() == before
        fabric._assert_indexes_consistent()


def test_down_links_remain_physical_and_occupied():
    fabric = network()
    fabric.set_link_state("L1", OperationalState.DOWN)
    assert fabric.find_link_by_endpoint(port("leaf-A", 1)).state == OperationalState.DOWN
    assert fabric.get_neighbors("leaf-A") == ("spine-1", "spine-2")
    assert fabric.get_neighbors("leaf-A", operational_only=True) == ("spine-2",)
    with pytest.raises(EndpointOccupiedError):
        fabric.add_link(port("leaf-A", 1), port("spine-2", 3), capacity_gbps=200, latency_us=1)
    fabric._assert_indexes_consistent()


def test_removal_and_parallel_links_update_indexes():
    fabric = network()
    link = fabric.add_link(port("leaf-A", 4), port("spine-1", 3), capacity_gbps=100, latency_us=0)
    assert link.id == "link-1"
    assert fabric.get_neighbors("leaf-A") == ("spine-1", "spine-2")
    with pytest.raises(DeviceInUseError):
        fabric.remove_switch("leaf-A")
    with pytest.raises(DeviceInUseError):
        fabric.remove_server("gpu-A")
    fabric.remove_link("L1")
    assert fabric.get_neighbors("leaf-A") == ("spine-1", "spine-2")
    fabric.remove_link("link-1")
    assert fabric.get_neighbors("leaf-A") == ("spine-2",)
    assert fabric.find_link_by_endpoint(port("leaf-A", 1)) is None
    assert fabric.find_link_by_endpoint(port("leaf-A", 4)) is None
    with pytest.raises(UnknownLinkError):
        fabric.remove_link("missing")
    fabric._assert_indexes_consistent()


def test_incremental_partial_topologies_and_device_removal():
    fabric = LeafSpineTopology()
    fabric.add_switch(Switch("leaf", SwitchRole.LEAF, CONFIG))
    fabric.add_switch(Switch("spine", SwitchRole.SPINE, CONFIG))
    fabric.add_server(GpuServer("gpu", 7, 100))
    assert fabric.validate_structure()
    assert fabric.get_neighbors("leaf") == ()
    assert fabric.connected_servers("leaf") == ()
    fabric.remove_switch("spine")
    fabric.remove_server("gpu")
    assert fabric.servers() == ()
    with pytest.raises(UnknownDeviceError):
        fabric.get_server("gpu")
    fabric._assert_indexes_consistent()


def test_duplicate_switch_server_and_node_ids():
    fabric = LeafSpineTopology()
    fabric.add_switch(Switch("leaf", SwitchRole.LEAF, CONFIG))
    fabric.add_server(GpuServer("gpu", 8, 100))
    with pytest.raises(DuplicateIdError):
        fabric.add_switch(Switch("leaf", SwitchRole.SPINE, CONFIG))
    with pytest.raises(DuplicateIdError):
        fabric.add_server(GpuServer("gpu2", 8, 100))
    with pytest.raises(DuplicateIdError):
        fabric.add_server(GpuServer("gpu", 9, 100))
    fabric._assert_indexes_consistent()


def test_fixture_paths_constraints_and_rerouting():
    fabric = network()
    same_leaf = fabric.find_path("leaf-A", "gpu-A")
    assert same_leaf.link_ids == ("L5",)
    assert same_leaf.total_latency_us == 1
    cross_leaf = fabric.find_path("leaf-A", "gpu-B")
    assert cross_leaf.link_ids == ("L1", "L2", "L6")
    assert cross_leaf.total_latency_us == 5
    assert cross_leaf.bottleneck_gbps == 100
    assert fabric.find_path("leaf-A", "gpu-B", max_total_latency_us=4) is None
    assert fabric.find_path("leaf-A", "gpu-B", min_link_capacity_gbps=150) is None
    fabric.set_link_state("L1", OperationalState.DOWN)
    assert fabric.find_path("leaf-A", "gpu-B").link_ids == ("L3", "L4", "L6")
    fabric.set_link_state("L3", OperationalState.DOWN)
    assert fabric.find_path("leaf-A", "gpu-B") is None
    fabric._assert_indexes_consistent()


def test_operational_state_changes_are_controlled_and_do_not_free_ports():
    fabric = network()
    operations = [
        lambda: fabric.set_port_state("leaf-A", 3, OperationalState.DOWN),
        lambda: fabric.set_switch_state("leaf-A", OperationalState.DOWN),
        lambda: fabric.set_server_state("gpu-A", OperationalState.DOWN),
        lambda: fabric.set_nic_state("gpu-A", OperationalState.DOWN),
        lambda: fabric.set_link_state("L5", OperationalState.DOWN),
    ]
    reset = [
        lambda: fabric.set_port_state("leaf-A", 3, OperationalState.UP),
        lambda: fabric.set_switch_state("leaf-A", OperationalState.UP),
        lambda: fabric.set_server_state("gpu-A", OperationalState.UP),
        lambda: fabric.set_nic_state("gpu-A", OperationalState.UP),
        lambda: fabric.set_link_state("L5", OperationalState.UP),
    ]
    for turn_down, turn_up in zip(operations, reset):
        turn_down()
        assert fabric.find_path("leaf-A", "gpu-A") is None
        assert fabric.find_link_by_endpoint(port("leaf-A", 3)).id == "L5"
        turn_up()
        assert fabric.find_path("leaf-A", "gpu-A") is not None
    fabric._assert_indexes_consistent()


def test_unknown_and_invalid_queries():
    fabric = network()
    with pytest.raises(UnknownDeviceError):
        fabric.find_path("not-a-switch", "gpu-A")
    with pytest.raises(UnknownDeviceError):
        fabric.find_path("leaf-A", "not-a-server")
    with pytest.raises(InvalidConnectionError):
        fabric.connected_servers("spine-1")
    for value in (-1, inf, nan, True):
        with pytest.raises(ValueError):
            fabric.find_path("leaf-A", "gpu-A", max_total_latency_us=value)
        with pytest.raises(ValueError):
            fabric.find_path("leaf-A", "gpu-A", min_link_capacity_gbps=value)


def test_equal_cost_ties_are_stable_across_insertion_orders():
    for backwards in (False, True):
        fabric = LeafSpineTopology()
        devices = [Switch("leaf", SwitchRole.LEAF, CONFIG), Switch("spine-a", SwitchRole.SPINE, CONFIG),
                   Switch("spine-b", SwitchRole.SPINE, CONFIG)]
        for device in reversed(devices) if backwards else devices:
            fabric.add_switch(device)
        fabric.add_server(GpuServer("gpu", 2, 100))
        pairs = [
            ("A", port("leaf", 1), port("spine-a", 1), 2),
            ("B", port("leaf", 2), port("spine-b", 1), 1),
            ("C", port("leaf", 3), nic("gpu"), 1),
        ]
        for link_id, a, b, latency in reversed(pairs) if backwards else pairs:
            fabric.add_link(a, b, capacity_gbps=100, latency_us=latency, link_id=link_id)
        # No other leaf: the direct one-hop route always wins (and zero latency is allowed).
        assert fabric.find_path("leaf", "gpu").link_ids == ("C",)
        fabric._assert_indexes_consistent()


def test_zero_latency_and_immutable_result():
    fabric = LeafSpineTopology()
    fabric.add_switch(Switch("leaf", SwitchRole.LEAF, CONFIG))
    fabric.add_server(GpuServer("gpu", 1, 100))
    fabric.add_link(port("leaf", 1), nic("gpu"), capacity_gbps=100, latency_us=0)
    result = fabric.find_path("leaf", "gpu", max_total_latency_us=0)
    assert result.total_latency_us == 0
    with pytest.raises(FrozenInstanceError):
        result.total_latency_us = 4
    fabric._assert_indexes_consistent()
