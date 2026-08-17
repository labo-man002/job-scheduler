"""Shared, size-configurable DB-row builders for integration tests.
Every function just db.add()+db.flush()s -- the caller's `db` fixture owns
the transaction and rolls it back, so nothing here needs its own cleanup.
"""

from app import models
from app.enums import ClientStatus, NodeStatus, ResourceStatus, ResourceType, TopologyType


def create_institute_and_client(db, owner="alice", institute_name="Test Institute"):
    institute = models.Institute(institute_name=institute_name)
    db.add(institute)
    db.flush()
    client = models.Client(owner=owner, institute_id=institute.institute_id, client_status=ClientStatus.ONLINE)
    db.add(client)
    db.flush()
    return institute, client


def create_cluster_with_nodes(
    db,
    node_count=4,
    resources_per_node=2,
    resource_type=ResourceType.CPU,
    topology_type=TopologyType.RING,
    cluster_name="test-cluster",
    wrap=True,
):
    """Total capacity = node_count * resources_per_node."""
    cluster = models.Cluster(cluster_name=cluster_name, topology_type=topology_type, dimension=[node_count], wrap=wrap)
    db.add(cluster)
    db.flush()

    nodes = []
    for i in range(node_count):
        node = models.Node(cluster_id=cluster.cluster_id, coordinates=[i], status=NodeStatus.IDLE)
        db.add(node)
        db.flush()
        for r in range(resources_per_node):
            db.add(models.ResourceNode(
                node_id=node.node_id, resource_type=resource_type,
                resource_type_index=r, resource_status=ResourceStatus.AVAILABLE,
            ))
        nodes.append(node)
    db.flush()
    return cluster, nodes
