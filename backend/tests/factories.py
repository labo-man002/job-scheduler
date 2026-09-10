from app import models
from app.enums import NodeStatus, ResourceStatus, ResourceType, TopologyType
from app.enums.priority import Priority


def make_node(node_id, coordinates, resource_count=4, resource_type=ResourceType.CPU, status=NodeStatus.IDLE):
    node = models.Node(node_id=node_id, cluster_id=1, coordinates=coordinates, status=status)
    node.resources = [
        models.ResourceNode(
            resource_node_id=node_id * 100 + i,
            node_id=node_id,
            resource_type=resource_type,
            resource_type_index=i,
            resource_status=ResourceStatus.AVAILABLE,
        )
        for i in range(resource_count)
    ]
    return node


def make_job(job_id,priority =Priority.LOW  , resource_type=ResourceType.CPU, amount=1):
    job = models.Job(job_id=job_id,priority = priority , duration=10, client_id=1)
    job.requirements = [
        models.ResourceRequirement(
            req_res_id=job_id, job_id=job_id, resource_type=resource_type, amount=amount
        )
    ]
    return job


def make_cluster(cluster_id, dimension, wrap, topology_type=TopologyType.RING):
    return models.Cluster(
        cluster_id=cluster_id,
        cluster_name=f"cluster-{cluster_id}",
        topology_type=topology_type,
        dimension=dimension,
        wrap=wrap,
    )
