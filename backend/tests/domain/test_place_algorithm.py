from app.domain.place_algorithm import PackAlgorithm, SpreadAlgorithm
from app.domain.topology import Topology
from app.enums import NodeStatus
from tests.factories import make_cluster, make_job, make_node


def test_tie_break_is_lowest_node_id_when_nothing_occupied():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    view = Topology(cluster).build_view(nodes)
    job = make_job(1)

    assert PackAlgorithm().select(nodes, job, view).node_id == 0
    assert SpreadAlgorithm().select(nodes, job, view).node_id == 0


def test_pack_prefers_closest_to_occupied_node():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    nodes[0].status = NodeStatus.ALLOCATED
    view = Topology(cluster).build_view(nodes)
    job = make_job(1)

    candidates = [n for n in nodes if n.node_id != 0]
    chosen = PackAlgorithm().select(candidates, job, view)
    assert chosen.node_id in (1, 7)


def test_spread_prefers_farthest_from_occupied_node():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    nodes[0].status = NodeStatus.ALLOCATED
    view = Topology(cluster).build_view(nodes)
    job = make_job(1)

    candidates = [n for n in nodes if n.node_id != 0]
    chosen = SpreadAlgorithm().select(candidates, job, view)
    assert chosen.node_id == 4


def test_mixed_node_counts_as_occupied_for_pack():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    nodes[0].status = NodeStatus.MIXED
    view = Topology(cluster).build_view(nodes)
    job = make_job(1)

    candidates = [n for n in nodes if n.node_id != 0]
    chosen = PackAlgorithm().select(candidates, job, view)
    assert chosen.node_id in (1, 7)


def test_pack_and_spread_can_pick_different_nodes():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    nodes[0].status = NodeStatus.ALLOCATED
    view = Topology(cluster).build_view(nodes)
    job = make_job(1)

    candidates = [n for n in nodes if n.node_id != 0]
    pack_choice = PackAlgorithm().select(candidates, job, view)
    spread_choice = SpreadAlgorithm().select(candidates, job, view)
    assert pack_choice.node_id != spread_choice.node_id
