import pytest

from app import models
from app.domain.topology import Topology
from app.enums import TopologyType
from tests.factories import make_cluster, make_node


def test_ring_wraps_at_boundary():
    cluster = make_cluster(1, dimension=[8], wrap=True)
    nodes = [make_node(i, [i]) for i in range(8)]
    view = Topology(cluster).build_view(nodes)

    assert view.distance(nodes[0], nodes[7]) == 1
    assert {n.node_id for n in view.neighbors(nodes[0])} == {1, 7}


def test_mesh_does_not_wrap():
    cluster = make_cluster(1, dimension=[8], wrap=False, topology_type=TopologyType.MESH_2D)
    nodes = [make_node(i, [i]) for i in range(8)]
    view = Topology(cluster).build_view(nodes)

    assert view.distance(nodes[0], nodes[7]) == 7
    assert {n.node_id for n in view.neighbors(nodes[0])} == {1}
    assert {n.node_id for n in view.neighbors(nodes[7])} == {6}


def test_3d_torus_wraps_on_every_axis():
    cluster = make_cluster(1, dimension=[4, 4, 4], wrap=True, topology_type=TopologyType.TORUS_3D)
    by_coords = {}
    for x in range(4):
        for y in range(4):
            for z in range(4):
                by_coords[(x, y, z)] = make_node(x * 16 + y * 4 + z, [x, y, z])
    view = Topology(cluster).build_view(list(by_coords.values()))

    origin = by_coords[(0, 0, 0)]
    far_corner = by_coords[(3, 3, 3)]

    assert view.distance(origin, far_corner) == 3  # one wraparound hop per axis
    assert len(view.neighbors(origin)) == 6  # 2 directions * 3 axes, all wrap


def test_fat_tree_is_not_implemented():
    cluster = make_cluster(1, dimension=[4, 4], wrap=False, topology_type=TopologyType.FAT_TREE)
    nodes = [make_node(0, [0, 0]), make_node(1, [0, 1])]
    view = Topology(cluster).build_view(nodes)

    with pytest.raises(NotImplementedError):
        view.distance(nodes[0], nodes[1])

    with pytest.raises(NotImplementedError):
        view.neighbors(nodes[0])


def test_mesh_with_wrap_is_rejected():
    cluster = make_cluster(1, dimension=[4, 4], wrap=True, topology_type=TopologyType.MESH_2D)
    with pytest.raises(ValueError):
        Topology(cluster)


def test_node_coordinates_length_must_match_cluster_dimension():
    cluster = make_cluster(1, dimension=[4, 4], wrap=True, topology_type=TopologyType.TORUS_2D)
    with pytest.raises(ValueError):
        models.Node(node_id=0, cluster=cluster, coordinates=[0])


def test_node_coordinate_out_of_bounds_is_rejected():
    cluster = make_cluster(1, dimension=[4], wrap=True, topology_type=TopologyType.RING)
    with pytest.raises(ValueError):
        models.Node(node_id=0, cluster=cluster, coordinates=[10])
