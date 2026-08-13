"""Round-trips data through the real Postgres DB to verify relationships resolve
correctly end to end. Requires Postgres up and reachable via .env (see CLAUDE.md);
skips instead of failing hard if it isn't. Every test rolls back its own session,
so nothing persists.
"""

import pytest
from sqlalchemy.exc import OperationalError

from app import models
from app.database import SessionLocal
from app.enums import ClientStatus, NodeStatus, ResourceStatus, ResourceType, TopologyType


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        session.execute(models.Institute.__table__.select().limit(0))
    except OperationalError:
        session.close()
        pytest.skip("Postgres not reachable — check .env and that the DB is running")
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seeded(db):
    institute = models.Institute(institute_name="Test Institute")
    db.add(institute)
    db.flush()

    client = models.Client(owner="alice", institute_id=institute.institute_id, client_status=ClientStatus.ONLINE)
    db.add(client)
    db.flush()

    cluster = models.Cluster(cluster_name="grid", topology_type=TopologyType.TORUS_2D, dimension=[4, 4], wrap=True)
    db.add(cluster)
    db.flush()

    node = models.Node(cluster_id=cluster.cluster_id, coordinates=[0, 0], status=NodeStatus.IDLE)
    db.add(node)
    db.flush()

    for i in range(4):
        db.add(models.ResourceNode(
            node_id=node.node_id,
            resource_type=ResourceType.CPU,
            resource_type_index=i,
            resource_status=ResourceStatus.AVAILABLE,
        ))
    db.flush()

    job = models.Job(duration=10, client_id=client.client_id)
    db.add(job)
    db.flush()

    db.add(models.ResourceRequirement(job_id=job.job_id, resource_type=ResourceType.CPU, amount=2))
    db.flush()

    db.expire_all()  # force a real reload from the DB on next attribute access, not cached Python state

    return {
        "institute_id": institute.institute_id,
        "client_id": client.client_id,
        "cluster_id": cluster.cluster_id,
        "node_id": node.node_id,
        "job_id": job.job_id,
    }


def test_cluster_to_nodes(db, seeded):
    cluster = db.query(models.Cluster).filter_by(cluster_id=seeded["cluster_id"]).one()
    assert [n.node_id for n in cluster.nodes] == [seeded["node_id"]]


def test_node_to_cluster_reverse(db, seeded):
    node = db.query(models.Node).filter_by(node_id=seeded["node_id"]).one()
    assert node.cluster.cluster_name == "grid"


def test_node_resources_and_free_resources(db, seeded):
    node = db.query(models.Node).filter_by(node_id=seeded["node_id"]).one()
    assert len(node.resources) == 4
    assert len(node.free_resources(ResourceType.CPU)) == 4


def test_job_to_requirements(db, seeded):
    job = db.query(models.Job).filter_by(job_id=seeded["job_id"]).one()
    assert [(r.resource_type, r.amount) for r in job.requirements] == [(ResourceType.CPU, 2)]


def test_job_to_client_to_institute(db, seeded):
    job = db.query(models.Job).filter_by(job_id=seeded["job_id"]).one()
    assert job.client.owner == "alice"
    assert job.client.institute.institute_name == "Test Institute"


def test_institute_to_clients_reverse(db, seeded):
    institute = db.query(models.Institute).filter_by(institute_id=seeded["institute_id"]).one()
    assert [c.owner for c in institute.clients] == ["alice"]
