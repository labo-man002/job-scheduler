import pytest
from sqlalchemy.exc import OperationalError

from app import models
from app.database import SessionLocal
from app.domain.server import ClientNotFoundError, JobNotFoundError, JobNotRunningError, JobTooLargeError, Server
from app.enums import AllocationStatus, JobStatus, Priority, ResourceStatus, ResourceType

from .db_factories import create_cluster_with_nodes, create_institute_and_client


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
def seeded_cluster(db):
    """Default size: 4 nodes * 2 CPUs = 8 total capacity, one client. Use
    db_factories directly in a test that needs a different size."""
    _, client = create_institute_and_client(db)
    cluster, nodes = create_cluster_with_nodes(db, node_count=4, resources_per_node=2)
    return {"client_id": client.client_id, "cluster_id": cluster.cluster_id, "nodes": nodes}


def test_submit_job_places_immediately_when_capacity_available(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"],
        requirements=[(ResourceType.CPU, 2)],
        priority=Priority.NORMAL,
        duration=10,
    )
    db.flush()

    assert job.status == JobStatus.RUNNING
    allocation = server.get_allocation_details(job.job_id)
    assert allocation is not None
    assert len(allocation.allocation_nodes) == 2


def test_submit_job_stays_queued_when_nothing_fits(db, seeded_cluster):
    server = Server(db)
    filler = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert filler.status == JobStatus.RUNNING

    job = server.submit_job(
        client_id=seeded_cluster["client_id"],
        requirements=[(ResourceType.CPU, 2)],  # fits the cluster in theory, nothing free right now
        priority=Priority.NORMAL,
        duration=10,
    )
    db.flush()

    assert job.status == JobStatus.QUEUED
    assert server.get_allocation_details(job.job_id) is None


def test_submit_job_rejects_job_too_large_for_any_cluster(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(JobTooLargeError):
        server.submit_job(
            client_id=seeded_cluster["client_id"],
            requirements=[(ResourceType.CPU, 100)],  # exceeds total cluster capacity (8), not just what's free
            priority=Priority.NORMAL,
            duration=10,
        )


def test_submit_job_rejects_unknown_client(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(ClientNotFoundError):
        server.submit_job(client_id=999999, requirements=[(ResourceType.CPU, 1)], priority=Priority.NORMAL, duration=10)


def test_cancel_queued_job_marks_cancelled_without_touching_resources(db, seeded_cluster):
    server = Server(db)
    server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert job.status == JobStatus.QUEUED

    server.cancel_job(job.job_id)
    db.flush()
    assert job.status == JobStatus.CANCELLED


def test_cancel_running_job_releases_resources(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert job.status == JobStatus.RUNNING
    allocation = server.get_allocation_details(job.job_id)
    resource_ids = [an.resource_node_id for an in allocation.allocation_nodes]

    server.cancel_job(job.job_id)
    db.flush()

    assert job.status == JobStatus.CANCELLED
    db.expire_all()
    released = db.query(models.ResourceNode).filter(models.ResourceNode.resource_node_id.in_(resource_ids)).all()
    assert all(r.resource_status == ResourceStatus.AVAILABLE for r in released)


def test_cancel_running_job_unblocks_a_queued_job(db, seeded_cluster):
    server = Server(db)
    # Fill the whole cluster (4 nodes * 2 CPUs = 8) with one job.
    big_job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert big_job.status == JobStatus.RUNNING

    # Nothing free now, so this one queues.
    small_job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert small_job.status == JobStatus.QUEUED

    # Freeing the big job's resources should let the queued one place itself.
    server.cancel_job(big_job.job_id)
    db.flush()
    db.expire_all()

    assert small_job.status == JobStatus.RUNNING


def test_cancel_unknown_job_raises(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(JobNotFoundError):
        server.cancel_job(999999)


def test_get_allocation_details_none_for_job_without_allocation(db, seeded_cluster):
    server = Server(db)
    server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert server.get_allocation_details(job.job_id) is None


def test_complete_running_job_records_duration_and_releases_resources(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    allocation = server.get_allocation_details(job.job_id)
    resource_ids = [an.resource_node_id for an in allocation.allocation_nodes]

    server.complete_job(job.job_id)
    db.flush()

    assert job.status == JobStatus.COMPLETED
    assert allocation.allocation_status == AllocationStatus.RELEASED
    assert allocation.end_time is not None
    assert allocation.duration is not None
    db.expire_all()
    released = db.query(models.ResourceNode).filter(models.ResourceNode.resource_node_id.in_(resource_ids)).all()
    assert all(r.resource_status == ResourceStatus.AVAILABLE for r in released)


def test_complete_job_rejects_non_running_job(db, seeded_cluster):
    server = Server(db)
    server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert job.status == JobStatus.QUEUED

    with pytest.raises(JobNotRunningError):
        server.complete_job(job.job_id)


def test_complete_job_unblocks_a_queued_job(db, seeded_cluster):
    server = Server(db)
    big_job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    small_job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert small_job.status == JobStatus.QUEUED

    server.complete_job(big_job.job_id)
    db.flush()
    db.expire_all()

    assert small_job.status == JobStatus.RUNNING


def test_cancel_running_job_also_records_duration(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    allocation = server.get_allocation_details(job.job_id)

    server.cancel_job(job.job_id)
    db.flush()

    assert allocation.end_time is not None
    assert allocation.duration is not None


def test_scheduler_is_shared_across_server_instances_for_same_cluster(db, seeded_cluster):
    """The whole point of owning a persistent Scheduler: two Server instances
    (standing in for two separate requests) must reuse the same one, per cluster."""
    first = Server(db)
    second = Server(db)
    cluster_id = seeded_cluster["cluster_id"]
    assert first._get_scheduler(cluster_id) is second._get_scheduler(cluster_id)


def test_cancelling_a_queued_job_does_not_block_jobs_behind_it(db, seeded_cluster):
    server = Server(db)
    # Fill the cluster so both submissions below queue up.
    filler = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert filler.status == JobStatus.RUNNING

    stale = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    behind_it = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    assert stale.status == JobStatus.QUEUED
    assert behind_it.status == JobStatus.QUEUED

    # Cancel the one at the head of the (shared, cross-request) queue while
    # it's still just queued -- its ref is now stale in the scheduler's heap.
    server.cancel_job(stale.job_id)
    db.flush()

    # Freeing the filler should place `behind_it`, lazily skipping the stale
    # ref rather than getting stuck behind it.
    server.complete_job(filler.job_id)
    db.flush()
    db.expire_all()

    assert behind_it.status == JobStatus.RUNNING


def test_jobs_route_to_best_fit_cluster_and_dont_block_each_other(db):
    _, client = create_institute_and_client(db)
    small_cluster, _ = create_cluster_with_nodes(db, node_count=2, resources_per_node=1, cluster_name="small")  # capacity 2
    large_cluster, _ = create_cluster_with_nodes(db, node_count=4, resources_per_node=4, cluster_name="large")  # capacity 16

    def submit(amount):
        job = server.submit_job(client_id=client.client_id, requirements=[(ResourceType.CPU, amount)], priority=Priority.NORMAL, duration=10)
        db.flush()
        return job

    def cluster_id_of(job):
        allocation = server.get_allocation_details(job.job_id)
        return allocation.allocation_nodes[0].resource_node.node.cluster_id

    server = Server(db)

    small_job = submit(1)
    large_job = submit(10)
    assert small_job.status == JobStatus.RUNNING
    assert large_job.status == JobStatus.RUNNING
    assert cluster_id_of(small_job) == small_cluster.cluster_id
    assert cluster_id_of(large_job) == large_cluster.cluster_id

    # Fill the small cluster's last unit and queue a job that can't fit there --
    # this must NOT block the large cluster's independent queue.
    fill_small = submit(1)
    assert fill_small.status == JobStatus.RUNNING
    stuck_on_small = submit(1)
    assert stuck_on_small.status == JobStatus.QUEUED

    another_large_job = submit(4)
    assert another_large_job.status == JobStatus.RUNNING
    assert cluster_id_of(another_large_job) == large_cluster.cluster_id
