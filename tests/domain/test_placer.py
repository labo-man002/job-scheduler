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

    assert pack_choice.node_id != spread_choice.node_id


def test_place_returns_none_when_nothing_fits():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=1) for i in range(4)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    job = make_job(1, amount=2)  # every node only has 1 free
    assert placer.place(job) is None


def test_place_reserves_resources_and_updates_node_status():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(4)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    chosen = placer.place(make_job(1, amount=2))

    assert chosen.node_id == 0
    assert chosen.status == NodeStatus.MIXED
    allocated = sum(1 for r in chosen.resources if r.resource_status == ResourceStatus.ALLOCATED)
    assert allocated == 2


def test_place_fills_node_fully_then_spills_to_neighbor():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(8)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    placer.place(make_job(1, amount=2))
    second = placer.place(make_job(2, amount=2))
    assert second.node_id == 0
    assert second.status == NodeStatus.ALLOCATED

    third = placer.place(make_job(3, amount=2))
    assert third.node_id in (1, 7)


def test_release_resource_restores_availability_and_status():
    cluster = make_cluster(1, dimension=[4], wrap=True)
    nodes = [make_node(i, [i], resource_count=4) for i in range(4)]
    placer = Placer(nodes, PackAlgorithm(), Topology(cluster))

    chosen = placer.place(make_job(1, amount=4))
    assert chosen.status == NodeStatus.ALLOCATED

    placer.release_resource(chosen.resources)
    assert chosen.status == NodeStatus.IDLE
    assert all(r.resource_status == ResourceStatus.AVAILABLE for r in chosen.resources)


def test_filter_nodes_excludes_insufficient_capacity():
    cluster = make_cluster(1, dimension=[2], wrap=True)
    small = make_node(0, [0], resource_count=1)
    big = make_node(1, [1], resource_count=4)
    placer = Placer([small, big], PackAlgorithm(), Topology(cluster))

    result = placer.filter_nodes([small, big], make_job(1, amount=2))
    assert result == [big]
