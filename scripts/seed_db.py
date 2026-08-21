"""Seeds the database with one cluster per supported topology type (RING,
TORUS_2D, MESH_2D, TORUS_3D), each with nodes/resources built through the
real Server.create_cluster path, then randomizes some resource allocations
and marks one node per cluster DOWN, so the frontend has something to look
at. FAT_TREE is skipped -- Server.create_cluster rejects it outright, there's
no coordinate/dimension model for it yet (see docs/decisions.md).

Also registers one institute, two clients, and submits a handful of jobs
through the real Server.submit_job path (so scheduling/placement actually
runs) -- gives the Jobs UI something real to show across QUEUED/RUNNING/
CANCELLED/COMPLETED.

Re-running this wipes any existing cluster/node/resource/job/client/institute
rows first. Run via the root package.json's seed:db script, which puts
backend/ on PYTHONPATH.
"""

import logging
import random

from app import models
from app.database import SessionLocal
from app.domain.server import NodeSpec, ResourceCount, Server
from app.enums.nodeStatus import NodeStatus
from app.enums.priority import Priority
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType
from app.enums.topologyType import TopologyType

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

random.seed(42)  # reproducible-but-varied demo data, not true randomness

RESOURCE_MIX = [
    (ResourceType.CPU, 32),
    (ResourceType.GPU, 4),
    (ResourceType.MEM, 8),
]

CLUSTERS = [
    dict(cluster_name="ring-a", topology_type=TopologyType.RING, dimension=[8], wrap=True),
    dict(cluster_name="torus2d-a", topology_type=TopologyType.TORUS_2D, dimension=[4, 4], wrap=True),
    dict(cluster_name="mesh2d-a", topology_type=TopologyType.MESH_2D, dimension=[3, 5], wrap=False),
    dict(cluster_name="torus3d-a", topology_type=TopologyType.TORUS_3D, dimension=[3, 3, 3], wrap=True),
]


def _grid_coords(dimension):
    if len(dimension) == 1:
        return [[x] for x in range(dimension[0])]
    if len(dimension) == 2:
        return [[x, y] for x in range(dimension[0]) for y in range(dimension[1])]
    return [[x, y, z] for x in range(dimension[0]) for y in range(dimension[1]) for z in range(dimension[2])]


def _node_specs(coords_list):
    return [
        NodeSpec(coordinates=coords, resources=[ResourceCount(resource_type=rt, count=count) for rt, count in RESOURCE_MIX])
        for coords in coords_list
    ]


def _recompute_node_status(node):
    """Mirrors app/domain/placer.py's Placer._recompute_status, so seeded data stays
    consistent with what the real placement path would produce."""
    statuses = {r.resource_status for r in node.resources}
    if not statuses or statuses == {ResourceStatus.AVAILABLE}:
        node.status = NodeStatus.IDLE
    elif statuses == {ResourceStatus.ALLOCATED}:
        node.status = NodeStatus.ALLOCATED
    else:
        node.status = NodeStatus.MIXED


def _randomize_allocations(cluster):
    """Pick each node's target status category first (IDLE/ALLOCATED/MIXED), then flip
    resources to match -- a single per-cluster fraction applied uniformly across every
    resource on every node almost always lands in MIXED, since a node here has ~40
    individually-rolled resources; picking the category first is what actually produces
    a visible spread across all four statuses."""
    for node in cluster.nodes:
        category = random.choices(["IDLE", "ALLOCATED", "MIXED"], weights=[0.4, 0.25, 0.35])[0]
        for resource in node.resources:
            if category == "IDLE":
                continue
            if category == "ALLOCATED" or random.random() < 0.5:
                resource.resource_status = ResourceStatus.ALLOCATED
        _recompute_node_status(node)


JOBS = [
    # (owner, priority, duration_minutes, requirements)
    ("alice", Priority.HIGH, 30, [(ResourceType.CPU, 4), (ResourceType.MEM, 2)]),
    ("alice", Priority.NORMAL, 120, [(ResourceType.GPU, 1), (ResourceType.CPU, 2)]),
    ("bob", Priority.URGENT, 15, [(ResourceType.CPU, 8)]),
    ("bob", Priority.LOW, 240, [(ResourceType.MEM, 4)]),
    ("bob", Priority.NORMAL, 60, [(ResourceType.GPU, 2), (ResourceType.MEM, 1)]),
]


def _seed_clients(db):
    server = Server(db)
    institute = server.register_institute(institute_name="Demo Institute")
    db.flush()
    clients = {
        owner: server.register_client(owner=owner, institute_id=institute.institute_id) for owner in {owner for owner, *_ in JOBS}
    }
    db.commit()
    return clients


def _seed_jobs(db, clients):
    server = Server(db)
    submitted = []
    for owner, priority, duration, requirements in JOBS:
        job = server.submit_job(client_id=clients[owner].client_id, requirements=requirements, priority=priority, duration=duration)
        db.commit()
        submitted.append(job)
        print(f"submitted job {job.job_id} for {owner}: {job.status.value}")

    # Give the status column some real variety beyond whatever QUEUED/RUNNING placement produced.
    queued = [j for j in submitted if j.status.value == "QUEUED"]
    running = [j for j in submitted if j.status.value == "RUNNING"]
    if queued:
        server.cancel_job(queued[0].job_id)
        db.commit()
        print(f"cancelled job {queued[0].job_id} (was QUEUED)")
    if running:
        server.complete_job(running[0].job_id)
        db.commit()
        print(f"completed job {running[0].job_id} (was RUNNING)")


def main():
    db = SessionLocal()
    try:
        existing_jobs = db.query(models.Job).count()
        if existing_jobs:
            print(f"found {existing_jobs} existing job(s) -- wiping job/client/institute tables first")
            db.query(models.JobEvent).delete()
            db.query(models.AllocationNode).delete()
            db.query(models.Allocation).delete()
            db.query(models.ResourceRequirement).delete()
            db.query(models.Job).delete()
            db.query(models.Client).delete()
            db.query(models.Institute).delete()
            db.commit()

        existing = db.query(models.Cluster).count()
        if existing:
            print(f"found {existing} existing cluster(s) -- wiping node_resource/node/cluster tables first")
            db.query(models.ResourceNode).delete()
            db.query(models.Node).delete()
            db.query(models.Cluster).delete()
            db.commit()

        server = Server(db)
        for spec in CLUSTERS:
            coords = _grid_coords(spec["dimension"])
            cluster = server.create_cluster(
                cluster_name=spec["cluster_name"],
                topology_type=spec["topology_type"],
                dimension=spec["dimension"],
                wrap=spec["wrap"],
                node_specs=_node_specs(coords),
            )
            db.flush()
            db.refresh(cluster)
            _randomize_allocations(cluster)

            down_node = random.choice(cluster.nodes)
            server.set_node_down(down_node.node_id)

            db.commit()
            print(f"created {cluster.cluster_name} ({spec['topology_type'].value}): {len(cluster.nodes)} nodes")

        print("FAT_TREE skipped -- not modeled yet (Server.create_cluster rejects it)")

        clients = _seed_clients(db)
        print(f"registered institute and {len(clients)} client(s): {', '.join(clients)}")
        _seed_jobs(db, clients)
    finally:
        db.close()


if __name__ == "__main__":
    main()
