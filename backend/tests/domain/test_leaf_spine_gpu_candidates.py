"""Read-only adapter tests: existing SQLAlchemy ResourceNode remains authoritative."""

import pytest

from app.domain.leaf_spine import (
    DeviceKind,
    EndpointRef,
    GpuCandidateFinder,
    InconsistentInventoryError,
    LeafSpineTopology,
    OperationalState,
    PortGroupConfig,
    Switch,
    SwitchHardwareConfig,
    SwitchRole,
)
from app.domain.server import Server
from app.enums import NodeStatus, ResourceStatus, ResourceType, TopologyType
from app.models.node import Node
from tests.factories import make_cluster, make_node


def fabric(nodes):
    topo = LeafSpineTopology()
    cfg = SwitchHardwareConfig("demo", (PortGroupConfig(4, 200),))
    topo.add_switch(Switch("leaf", SwitchRole.LEAF, cfg))
    for node in nodes:
        topo.add_node(node)
    for i, node in enumerate(nodes, start=1):
        topo.add_link(
            EndpointRef(DeviceKind.SWITCH, "leaf", f"p{i}"),
            EndpointRef(DeviceKind.NODE, str(node.node_id), "nic0"),
            capacity_gbps=100, latency_us=i,
            link_id=f"access-{i}",
        )
    return topo


def test_candidate_discovery_filters_by_real_gpu_units_without_mutation():
    n1 = make_node(10, [0], 3, ResourceType.GPU, nic_capacity_gbps=100)
    n2 = make_node(11, [1], 3, ResourceType.GPU, nic_capacity_gbps=100)
    topo = fabric([n1, n2])
    n1.resources[0].resource_status = ResourceStatus.ALLOCATED
    n2.resources[0].resource_status = ResourceStatus.UNAVAILABLE
    n2.resources[1].resource_status = ResourceStatus.ALLOCATED
    snapshot = [(n.status, tuple(r.resource_status for r in n.resources)) for n in (n1, n2)]
    finder = GpuCandidateFinder(topo)
    candidates = finder.find_candidates("leaf", [n2, n1], min_free_gpus_per_node=2)
    assert len(candidates) == 1
    assert candidates[0].node_id == 10
    assert candidates[0].free_gpu_ids == tuple(sorted(r.resource_node_id for r in n1.resources[1:]))
    assert candidates[0].free_gpu_count == 2
    assert snapshot == [(n.status, tuple(r.resource_status for r in n.resources)) for n in (n1, n2)]
    assert [c.node_id for c in finder.find_candidates("leaf", [n1, n2])] == [10, 11]
    assert finder.find_candidates("leaf", [n1, n2], min_link_capacity_gbps=101) == ()
    assert [c.node_id for c in finder.find_candidates("leaf", [n1, n2], max_total_latency_us=1)] == [10]
    topo.set_link_state("access-1", OperationalState.DOWN)
    assert finder.find_candidates("leaf", [n1, n2], min_free_gpus_per_node=2) == ()


def test_candidate_discovery_ignores_down_nodes():
    nodes = [
        make_node(10, [0], 2, ResourceType.GPU, NodeStatus.DOWN, nic_capacity_gbps=100),
        make_node(11, [1], 2, ResourceType.GPU, nic_capacity_gbps=100),
    ]
    topo = fabric(nodes)
    assert [c.node_id for c in GpuCandidateFinder(topo).find_candidates("leaf", nodes)] == [11]


def test_candidate_discovery_requires_gpu_resources_to_be_preloaded():
    node = Node(
        node_id=21,
        cluster_id=1,
        coordinates=[2],
        nic_capacity_gbps=100,
    )
    topo = fabric([node])
    with pytest.raises(InconsistentInventoryError, match="resources must be loaded"):
        GpuCandidateFinder(topo).find_candidates("leaf", [node])


def test_candidate_discovery_rejects_mismatched_and_duplicate_inventory():
    one = make_node(10, [0], 2, ResourceType.GPU, nic_capacity_gbps=100)
    two = make_node(11, [1], 2, ResourceType.GPU, nic_capacity_gbps=100)
    topo = fabric([one, two])
    finder = GpuCandidateFinder(topo)
    with pytest.raises(InconsistentInventoryError):
        finder.find_candidates("leaf", [one])
    with pytest.raises(InconsistentInventoryError):
        finder.find_candidates("leaf", [one, one])

    # Same primary key, but a different ORM instance is not the registered Node.
    detached_copy = make_node(10, [0], 2, ResourceType.GPU, nic_capacity_gbps=100)
    with pytest.raises(InconsistentInventoryError):
        finder.find_candidates("leaf", [detached_copy, two])
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], min_free_gpus_per_node=0)
    # Constraint validation must not depend on there being a candidate to score.
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], min_link_capacity_gbps=0)
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], min_link_capacity_gbps=True)
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], max_total_latency_us=-1)
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], max_total_latency_us=float("nan"))
    with pytest.raises(ValueError):
        finder.find_candidates("leaf", [], min_link_capacity_gbps=10**1000)



def test_leaf_spine_implements_generic_placement_topology_contract():
    from app.domain.topology import PlacementTopology, PlacementTopologyView

    first = make_node(30, [0], 1, ResourceType.GPU, nic_capacity_gbps=100)
    second = make_node(31, [1], 1, ResourceType.GPU, nic_capacity_gbps=100)
    topo = fabric([first, second])

    assert isinstance(topo, PlacementTopology)
    view = topo.build_view([first, second])
    assert isinstance(view, PlacementTopologyView)
    assert view.is_reachable(first, second)
    assert view.distance(first, second) == 3
    assert view.path_latency(first, second) == 3
    assert view.path_bandwidth(first, second) == 100


def test_leaf_spine_placement_view_rejects_unreachable_nodes():
    first = make_node(40, [0], 1, ResourceType.GPU, nic_capacity_gbps=100)
    second = make_node(41, [1], 1, ResourceType.GPU, nic_capacity_gbps=100)
    topo = LeafSpineTopology()
    topo.add_node(first)
    topo.add_node(second)
    view = topo.build_view([first, second])

    assert not view.is_reachable(first, second)
    assert view.distance(first, second) == float("inf")
    assert view.path_latency(first, second) is None
    assert view.path_bandwidth(first, second) is None



def test_leaf_spine_placement_view_accepts_reserved_node_subset():
    first = make_node(50, [0], 1, ResourceType.GPU, nic_capacity_gbps=100)
    second = make_node(51, [1], 1, ResourceType.GPU, nic_capacity_gbps=100)
    topo = fabric([first, second])

    view = topo.build_view([first])
    assert view.nodes == [first, second]



def test_persisted_leaf_spine_config_rebuilds_runtime_topology():
    first = make_node(60, [], 1, ResourceType.GPU, nic_capacity_gbps=100)
    second = make_node(61, [], 1, ResourceType.GPU, nic_capacity_gbps=100)
    cluster = make_cluster(1, [], False, topology_type=TopologyType.LEAF_SPINE)
    cluster.fabric_config = {
        "switches": [
            {
                "switch_id": "leaf-1",
                "role": "LEAF",
                "model": "demo",
                "port_groups": [{"count": 2, "speed_gbps": 200}],
            }
        ],
        "links": [
            {
                "link_id": "node-60",
                "a": {"device_kind": "SWITCH", "device_id": "leaf-1", "endpoint_id": "p1"},
                "b": {"device_kind": "NODE", "device_id": "60", "endpoint_id": "nic0"},
                "capacity_gbps": 100,
                "latency_us": 1,
            },
            {
                "link_id": "node-61",
                "a": {"device_kind": "SWITCH", "device_id": "leaf-1", "endpoint_id": "p2"},
                "b": {"device_kind": "NODE", "device_id": "61", "endpoint_id": "nic0"},
                "capacity_gbps": 100,
                "latency_us": 1,
            },
        ],
    }

    topology = Server._build_leaf_spine_topology(cluster, [first, second])
    view = topology.build_view([first, second])

    assert view.is_reachable(first, second)
    assert view.distance(first, second) == 2
    assert view.path_bandwidth(first, second) == 100
