from app.domain.leaf_spine import (
    DeviceKind,
    EndpointRef,
    LeafSpineTopology,
    PortGroupConfig,
    Switch,
    SwitchHardwareConfig,
    SwitchRole,
)
from app.domain.place_algorithm import PackAlgorithm, SpreadAlgorithm
from app.domain.placer import Placer
from app.domain.topology import Topology
from app.enums import NodeStatus, ResourceStatus, ResourceType
from tests.factories import make_cluster, make_job, make_node


def test_set_algorithm_changes_placement_behavior():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    placer = Placer([], PackAlgorithm(), Topology(cluster))

    pack_nodes = [make_node(i, [i]) for i in range(8)]
    pack_nodes[0].status = NodeStatus.ALLOCATED
    placer.nodes = pack_nodes
    pack_choice = placer.place(make_job(1))

    spread_nodes = [make_node(i, [i]) for i in range(8)]
    spread_nodes[0].status = NodeStatus.ALLOCATED
    placer.set_algorithm(SpreadAlgorithm())
    placer.nodes = spread_nodes
    spread_choice = placer.place(make_job(2))

    assert pack_choice[0].node.node_id != spread_choice[0].node.node_id


def test_place_reserves_resources_and_updates_node_status():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(4)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    reserved = placer.place(make_job(1, amount=2))

    assert len(reserved) == 2
    assert all(r.node.node_id == 0 for r in reserved)
    assert nodes[0].status == NodeStatus.MIXED
    assert all(r.resource_status == ResourceStatus.ALLOCATED for r in reserved)


def test_place_fills_node_fully_then_spills_to_neighbor():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(8)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    placer.place(make_job(1, amount=2))
    second = placer.place(make_job(2, amount=2))
    assert second[0].node.node_id == 0
    assert nodes[0].status == NodeStatus.ALLOCATED

    third = placer.place(make_job(3, amount=2))
    assert third[0].node.node_id in (1, 7)


def test_place_spans_multiple_nodes_when_none_fit_alone():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=2) for i in range(4)]  # 2 CPUs/node, 8 total
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    reserved = placer.place(make_job(1, amount=3))  # no single node has 3

    assert len(reserved) == 3
    touched_nodes = {r.node.node_id for r in reserved}
    assert len(touched_nodes) >= 2  # had to span more than one node


def test_place_returns_none_when_cluster_wide_capacity_insufficient():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=1) for i in range(4)]  # 4 CPUs total

    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))
    assert placer.place(make_job(1, amount=5)) is None  # cluster only has 4
    assert all(r.resource_status == ResourceStatus.AVAILABLE for n in nodes for r in n.resources)


def test_release_resource_restores_availability_and_status():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(4)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    reserved = placer.place(make_job(1, amount=4))
    assert nodes[0].status == NodeStatus.ALLOCATED

    placer.release_resource(reserved)
    assert nodes[0].status == NodeStatus.IDLE
    assert all(r.resource_status == ResourceStatus.AVAILABLE for r in reserved)


def test_filter_nodes_excludes_insufficient_capacity():
    cluster = make_cluster(1, dimension=[2], wrap=True)
    small = make_node(0, [0], resource_count=1)
    big = make_node(1, [1], resource_count=4)
    placer = Placer([small, big], PackAlgorithm(), Topology(cluster))

    result = placer.filter_nodes([small, big], make_job(1, amount=2))
    assert result == [big]



def test_placer_uses_leaf_spine_topology_through_common_contract():
    nodes = [
        make_node(70, [0], resource_count=2, nic_capacity_gbps=100),
        make_node(71, [1], resource_count=2, nic_capacity_gbps=100),
    ]
    topology = LeafSpineTopology()
    topology.add_switch(
        Switch("leaf", SwitchRole.LEAF, SwitchHardwareConfig("test", (PortGroupConfig(4, 200),)))
    )
    for node in nodes:
        topology.add_node(node)
    for index, node in enumerate(nodes, start=1):
        topology.add_link(
            EndpointRef(DeviceKind.SWITCH, "leaf", f"p{index}"),
            EndpointRef(DeviceKind.NODE, str(node.node_id), "nic0"),
            capacity_gbps=100,
            latency_us=index,
        )

    nodes[0].status = NodeStatus.ALLOCATED
    placer = Placer(nodes, PackAlgorithm(), topology)

    reserved = placer.place(make_job(70))

    assert reserved is not None
    assert reserved[0].node is nodes[0]



def _leaf_fabric(nodes, capacities=None, latencies=None):
    topology = LeafSpineTopology()
    topology.add_switch(
        Switch("leaf", SwitchRole.LEAF, SwitchHardwareConfig("test", (PortGroupConfig(len(nodes), 200),)))
    )
    capacities = capacities or [100] * len(nodes)
    latencies = latencies or [1] * len(nodes)
    for node in nodes:
        topology.add_node(node)
    for index, node in enumerate(nodes):
        topology.add_link(
            EndpointRef(DeviceKind.SWITCH, "leaf", f"p{index + 1}"),
            EndpointRef(DeviceKind.NODE, str(node.node_id), "nic0"),
            capacity_gbps=capacities[index],
            latency_us=latencies[index],
        )
    return topology


def test_placer_automatically_spans_nodes_when_one_node_lacks_capacity():
    nodes = [make_node(80, [0], 2), make_node(81, [1], 2)]
    job = make_job(80, amount=3)
    placer = Placer(nodes, PackAlgorithm(), Topology(make_cluster(1, [2], False)))

    reserved = placer.place(job)

    assert reserved is not None
    assert {resource.node.node_id for resource in reserved} == {80, 81}
    assert len(reserved) == 3


def test_network_locality_can_prefer_more_nodes_than_the_minimum_feasible_group():
    nodes = [
        make_node(120, [0], 2, ResourceType.GPU, nic_capacity_gbps=100),
        make_node(121, [1], 2, ResourceType.GPU, nic_capacity_gbps=100),
        make_node(122, [2], 1, ResourceType.GPU, nic_capacity_gbps=100),
        make_node(123, [3], 1, ResourceType.GPU, nic_capacity_gbps=100),
    ]
    topology = _leaf_fabric(nodes, latencies=[1, 10, 1, 1])
    job = make_job(120, resource_type=ResourceType.GPU, amount=4)
    placer = Placer(nodes, PackAlgorithm(), topology)

    reserved = placer.place(job)

    assert reserved is not None
    # Node 120 + 121 can provide four GPUs, but their path costs 11.
    # Nodes 120 + 122 + 123 provide the same four GPUs with total
    # pairwise path cost 6, so locality wins over using fewer Nodes.
    assert {resource.node.node_id for resource in reserved} == {120, 122, 123}


def test_placer_always_rejects_disconnected_group_without_partial_reservation():
    nodes = [
        make_node(90, [0], 2, nic_capacity_gbps=100),
        make_node(91, [1], 2, nic_capacity_gbps=100),
    ]
    topology = LeafSpineTopology()
    topology.add_node(nodes[0])
    topology.add_node(nodes[1])
    job = make_job(90, amount=3)
    job.require_full_connectivity = True
    placer = Placer(nodes, PackAlgorithm(), topology)

    assert placer.place(job) is None
    assert all(resource.resource_status == ResourceStatus.AVAILABLE for node in nodes for resource in node.resources)


def test_placer_uses_path_latency_for_locality_without_job_thresholds():
    nodes = [
        make_node(100, [0], 2, nic_capacity_gbps=100),
        make_node(101, [1], 2, nic_capacity_gbps=100),
    ]
    topology = _leaf_fabric(nodes, capacities=[100, 50], latencies=[1, 2])
    job = make_job(100, amount=3)
    placer = Placer(nodes, PackAlgorithm(), topology)

    reserved = placer.place(job)

    # No per-Job bandwidth/latency thresholds exist. A reachable path is
    # sufficient; its latency is used only to rank candidate groups.
    assert reserved is not None
    assert len(reserved) == 3



def test_placer_discovers_and_places_gpu_resources_through_leaf_spine_topology():
    nodes = [
        make_node(110, [0], resource_count=2, resource_type=ResourceType.GPU, nic_capacity_gbps=100),
        make_node(111, [1], resource_count=2, resource_type=ResourceType.GPU, nic_capacity_gbps=100),
    ]
    topology = _leaf_fabric(nodes)
    job = make_job(110, resource_type=ResourceType.GPU, amount=3)
    job.require_full_connectivity = True
    placer = Placer(nodes, PackAlgorithm(), topology)

    candidates = placer.find_candidates(job)
    assert candidates == nodes

    reserved = placer.place(job)

    assert reserved is not None
    assert len(reserved) == 3
    assert all(resource.resource_type == ResourceType.GPU for resource in reserved)
    assert {resource.node.node_id for resource in reserved} == {110, 111}
    assert all(resource.resource_status == ResourceStatus.ALLOCATED for resource in reserved)
