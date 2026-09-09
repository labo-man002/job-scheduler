from app.domain.place_algorithm import PackAlgorithm, SpreadAlgorithm
from app.domain.placer import Placer
from app.domain.topology import Topology
from app.enums import NodeStatus, ResourceStatus
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
