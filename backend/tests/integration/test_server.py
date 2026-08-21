from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app import models
from app.database import SessionLocal
from app.domain.exceptions import (
    ClientNotFoundError,
    ClusterNotFoundError,
    InstituteNotFoundError,
    JobNotFoundError,
    JobNotRunningError,
    JobTooLargeError,
    NodeNotFoundError,
    NodeNotInClusterError,
    QuotaExceededError,
    QuotaNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from app.domain.server import NodeSpec, ResourceCount, Server
from app.enums import (
    AllocationStatus,
    ClientStatus,
    JobStatus,
    NodeStatus,
    Priority,
    ResourceStatus,
    ResourceType,
    TopologyType,
)

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
    institute, client = create_institute_and_client(db)
    cluster, nodes = create_cluster_with_nodes(db, node_count=4, resources_per_node=2)
    return {
        "institute_id": institute.institute_id,
        "client_id": client.client_id,
        "cluster_id": cluster.cluster_id,
        "nodes": nodes,
    }


def test_register_client_creates_client_offline_by_default(db):
    institute, _ = create_institute_and_client(db)
    server = Server(db)

    client = server.register_client(owner="bob", institute_id=institute.institute_id)
    db.flush()

    assert client.client_id is not None
    assert client.owner == "bob"
    assert client.institute_id == institute.institute_id
    assert client.client_status == ClientStatus.OFFLINE


def test_submit_job_marks_client_online(db, seeded_cluster):
    server = Server(db)
    client = server.register_client(owner="fresh", institute_id=seeded_cluster["institute_id"])
    db.flush()
    assert client.client_status == ClientStatus.OFFLINE

    server.submit_job(
        client_id=client.client_id, requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )

    assert client.client_status == ClientStatus.ONLINE


def test_register_client_rejects_unknown_institute(db):
    server = Server(db)
    with pytest.raises(InstituteNotFoundError):
        server.register_client(owner="bob", institute_id=999999)


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
            # Deliberately absurd, not just "bigger than this fixture's 8-unit cluster" --
            # this must stay too large even against real demo data seeded into the same dev
            # DB (e.g. via scripts/seed_db.py), since _best_fit_cluster scans every cluster
            # in the database, not just this test's own fixture.
            requirements=[(ResourceType.CPU, 10_000_000_000)],
            priority=Priority.NORMAL,
            duration=10,
        )


def test_submit_job_rejects_unknown_client(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(ClientNotFoundError):
        server.submit_job(client_id=999999, requirements=[(ResourceType.CPU, 1)], priority=Priority.NORMAL, duration=10)


def test_submit_job_rejects_duplicate_resource_type(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(ValueError):
        server.submit_job(
            client_id=seeded_cluster["client_id"],
            requirements=[(ResourceType.CPU, 2), (ResourceType.CPU, 3)],
            priority=Priority.NORMAL,
            duration=10,
        )


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


def test_submit_job_with_no_quota_configured_is_unrestricted(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    assert job.status == JobStatus.RUNNING


def test_quota_blocks_submission_once_exceeded(db, seeded_cluster):
    db.add(models.Quota(
        resource_type=ResourceType.CPU, institute_id=seeded_cluster["institute_id"], limit=4,
        period=datetime.now(timezone.utc),  # this calendar month -- _check_quota only looks at the current month's row
    ))
    db.flush()
    server = Server(db)

    within_quota = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 3)], priority=Priority.NORMAL, duration=10
    )
    assert within_quota.status == JobStatus.RUNNING  # 3/4 used

    with pytest.raises(QuotaExceededError):
        server.submit_job(
            client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
        )  # 3 + 2 = 5 > 4


def test_create_quota_defaults_to_current_month(db, seeded_cluster):
    server = Server(db)
    now = datetime.now(timezone.utc)

    quota = server.create_quota(institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=4)

    assert quota.period.year == now.year
    assert quota.period.month == now.month


def test_create_quota_upserts_within_the_same_month(db, seeded_cluster):
    server = Server(db)
    first = server.create_quota(institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=4)
    second = server.create_quota(institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=10)

    assert first.id == second.id
    all_quotas = db.query(models.Quota).filter_by(institute_id=seeded_cluster["institute_id"]).all()
    assert len(all_quotas) == 1
    assert all_quotas[0].limit == 10


def test_quota_from_a_different_month_does_not_apply(db, seeded_cluster):
    now = datetime.now(timezone.utc)
    last_month = now.replace(day=1) - timedelta(days=1)  # some day in the previous calendar month
    server = Server(db)
    server.create_quota(institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=1, period=last_month)

    # This month has no quota row of its own -- unrestricted, same as no quota at all.
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    assert job.status == JobStatus.RUNNING


def test_create_quota_for_a_future_month(db, seeded_cluster):
    now = datetime.now(timezone.utc)
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    server = Server(db)

    quota = server.create_quota(
        institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=4, period=next_month
    )

    assert quota.period.month == next_month.month
    # This month is unaffected by next month's quota.
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    assert job.status == JobStatus.RUNNING


def test_reservation_blocks_other_institutes_but_not_the_owner(db):
    reserving_institute, reserving_client = create_institute_and_client(db, owner="owner")
    other_institute, other_client = create_institute_and_client(db, owner="other", institute_name="Other Institute")
    cluster, nodes = create_cluster_with_nodes(db, node_count=1, resources_per_node=2)  # exactly one node, capacity 2

    reservation = models.Reservation(
        institute_id=reserving_institute.institute_id,
        start_period=datetime.now(timezone.utc) - timedelta(hours=1),
        end_period=datetime.now(timezone.utc) + timedelta(hours=1),
        reason="test",
    )
    db.add(reservation)
    db.flush()
    db.add(models.NodeReservation(node_id=nodes[0].node_id, reservation_id=reservation.id))
    db.flush()

    server = Server(db)

    blocked = server.submit_job(
        client_id=other_client.client_id, requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    assert blocked.status == JobStatus.QUEUED  # the only node is reserved for someone else

    allowed = server.submit_job(
        client_id=reserving_client.client_id, requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    assert allowed.status == JobStatus.RUNNING  # the reservation is theirs


def test_register_institute_creates_institute(db):
    server = Server(db)
    institute = server.register_institute("New Institute")
    db.flush()

    assert institute.institute_id is not None
    assert institute.institute_name == "New Institute"


def test_create_cluster_creates_nodes_and_resources(db):
    server = Server(db)
    cluster = server.create_cluster(
        cluster_name="api-cluster",
        topology_type=TopologyType.RING,
        dimension=[3],
        wrap=True,
        node_specs=[
            NodeSpec([0], [ResourceCount(ResourceType.CPU, 2)]),
            NodeSpec([1], [ResourceCount(ResourceType.CPU, 2), ResourceCount(ResourceType.GPU, 1)]),
            NodeSpec([2], [ResourceCount(ResourceType.CPU, 2)]),
        ],
    )
    db.flush()

    assert cluster.cluster_id is not None
    assert len(cluster.nodes) == 3
    assert cluster.total_capacity() == 7
    assert cluster.free_capacity() == 7
    middle = next(n for n in cluster.nodes if n.coordinates == [1])
    assert {r.resource_type for r in middle.resources} == {ResourceType.CPU, ResourceType.GPU}


def test_create_cluster_rejects_coordinate_dimension_mismatch(db):
    server = Server(db)
    with pytest.raises(ValueError):
        server.create_cluster(
            cluster_name="bad-cluster",
            topology_type=TopologyType.RING,
            dimension=[3],
            wrap=True,
            node_specs=[NodeSpec([0, 0], [ResourceCount(ResourceType.CPU, 1)])],  # 2 coords for a 1-axis dimension
        )


@pytest.mark.parametrize("topology_type,dimension", [
    (TopologyType.RING, [3, 3]),        # RING wants 1 axis
    (TopologyType.TORUS_2D, [3]),       # TORUS_2D wants 2 axes
    (TopologyType.MESH_2D, [3, 3, 3]),  # MESH_2D wants 2 axes
    (TopologyType.TORUS_3D, [3, 3]),    # TORUS_3D wants 3 axes
])
def test_create_cluster_rejects_wrong_axis_count(db, topology_type, dimension):
    """Server.create_cluster-only policy -- domain-layer tests bypass Server
    and can still construct a mismatched Cluster directly (see docs/decisions.md)."""
    server = Server(db)
    with pytest.raises(ValueError):
        server.create_cluster(
            cluster_name="bad-cluster", topology_type=topology_type, dimension=dimension, wrap=True,
            node_specs=[NodeSpec([0] * len(dimension), [ResourceCount(ResourceType.CPU, 1)])],
        )


def test_create_cluster_rejects_non_positive_dimension(db):
    server = Server(db)
    with pytest.raises(ValueError):
        server.create_cluster(
            cluster_name="bad-cluster", topology_type=TopologyType.RING, dimension=[0], wrap=True,
            node_specs=[NodeSpec([0], [ResourceCount(ResourceType.CPU, 1)])],
        )


def test_create_cluster_rejects_fat_tree(db):
    server = Server(db)
    with pytest.raises(ValueError):
        server.create_cluster(
            cluster_name="bad-cluster", topology_type=TopologyType.FAT_TREE, dimension=[3], wrap=False,
            node_specs=[NodeSpec([0], [ResourceCount(ResourceType.CPU, 1)])],
        )


def test_create_cluster_rejects_mesh_with_wrap(db):
    server = Server(db)
    with pytest.raises(ValueError):
        server.create_cluster(
            cluster_name="bad-cluster", topology_type=TopologyType.MESH_2D, dimension=[3, 3], wrap=True,
            node_specs=[NodeSpec([0, 0], [ResourceCount(ResourceType.CPU, 1)])],
        )


def test_create_cluster_allows_torus_without_wrap(db):
    server = Server(db)
    cluster = server.create_cluster(
        cluster_name="unwrapped-torus", topology_type=TopologyType.TORUS_3D, dimension=[2, 2, 2], wrap=False,
        node_specs=[NodeSpec([0, 0, 0], [ResourceCount(ResourceType.CPU, 1)])],
    )
    assert cluster.wrap is False


def test_create_quota_rejects_unknown_institute(db):
    server = Server(db)
    with pytest.raises(InstituteNotFoundError):
        server.create_quota(institute_id=999999, resource_type=ResourceType.CPU, limit=4)


def test_create_reservation_rejects_unknown_institute(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(InstituteNotFoundError):
        server.create_reservation(
            institute_id=999999,
            cluster_id=seeded_cluster["cluster_id"],
            node_ids=[seeded_cluster["nodes"][0].node_id],
            start_period=datetime.now(timezone.utc),
            end_period=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="test",
        )


def test_create_reservation_rejects_unknown_cluster(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(ClusterNotFoundError):
        server.create_reservation(
            institute_id=seeded_cluster["institute_id"],
            cluster_id=999999,
            node_ids=[seeded_cluster["nodes"][0].node_id],
            start_period=datetime.now(timezone.utc),
            end_period=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="test",
        )


def test_create_reservation_rejects_unknown_node(db, seeded_cluster):
    server = Server(db)
    with pytest.raises(NodeNotFoundError):
        server.create_reservation(
            institute_id=seeded_cluster["institute_id"],
            cluster_id=seeded_cluster["cluster_id"],
            node_ids=[999999],
            start_period=datetime.now(timezone.utc),
            end_period=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="test",
        )


def test_create_reservation_rejects_node_from_a_different_cluster(db, seeded_cluster):
    other_cluster, other_nodes = create_cluster_with_nodes(db, node_count=1, resources_per_node=1, cluster_name="other")
    server = Server(db)
    with pytest.raises(NodeNotInClusterError):
        server.create_reservation(
            institute_id=seeded_cluster["institute_id"],
            cluster_id=seeded_cluster["cluster_id"],
            node_ids=[other_nodes[0].node_id],  # belongs to other_cluster, not seeded_cluster
            start_period=datetime.now(timezone.utc),
            end_period=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="test",
        )


def test_create_reservation_rejects_overlap_with_another_institutes_reservation(db, seeded_cluster):
    other_institute, _ = create_institute_and_client(db, owner="other", institute_name="Other Institute")
    node_id = seeded_cluster["nodes"][0].node_id
    server = Server(db)
    server.create_reservation(
        institute_id=seeded_cluster["institute_id"],
        cluster_id=seeded_cluster["cluster_id"],
        node_ids=[node_id],
        start_period=datetime.now(timezone.utc),
        end_period=datetime.now(timezone.utc) + timedelta(hours=2),
        reason="first",
    )

    with pytest.raises(ReservationConflictError):
        server.create_reservation(
            institute_id=other_institute.institute_id,
            cluster_id=seeded_cluster["cluster_id"],
            node_ids=[node_id],
            start_period=datetime.now(timezone.utc) + timedelta(hours=1),  # overlaps the first reservation
            end_period=datetime.now(timezone.utc) + timedelta(hours=3),
            reason="second",
        )


def test_create_reservation_allows_same_institute_to_reserve_again(db, seeded_cluster):
    node_id = seeded_cluster["nodes"][0].node_id
    server = Server(db)
    server.create_reservation(
        institute_id=seeded_cluster["institute_id"],
        cluster_id=seeded_cluster["cluster_id"],
        node_ids=[node_id],
        start_period=datetime.now(timezone.utc),
        end_period=datetime.now(timezone.utc) + timedelta(hours=2),
        reason="first",
    )

    second = server.create_reservation(
        institute_id=seeded_cluster["institute_id"],
        cluster_id=seeded_cluster["cluster_id"],
        node_ids=[node_id],
        start_period=datetime.now(timezone.utc) + timedelta(hours=1),  # overlaps, but same institute
        end_period=datetime.now(timezone.utc) + timedelta(hours=3),
        reason="second",
    )
    assert second.id is not None


def test_list_clusters_returns_all(db, seeded_cluster):
    server = Server(db)
    clusters = server.list_clusters()
    assert seeded_cluster["cluster_id"] in [c.cluster_id for c in clusters]


def test_get_cluster_raises_for_unknown(db):
    server = Server(db)
    with pytest.raises(ClusterNotFoundError):
        server.get_cluster(999999)


def test_list_jobs_filters_by_client_and_status(db, seeded_cluster):
    server = Server(db)
    filler = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    queued = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()

    all_jobs = server.list_jobs(client_id=seeded_cluster["client_id"])
    assert {j.job_id for j in all_jobs} == {filler.job_id, queued.job_id}

    running_only = server.list_jobs(client_id=seeded_cluster["client_id"], status=JobStatus.RUNNING)
    assert [j.job_id for j in running_only] == [filler.job_id]


def test_job_events_recorded_through_submit_and_placement(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()

    event_types = [e.event_type for e in job.events]
    assert event_types == [JobStatus.QUEUED, JobStatus.RUNNING]


def test_job_events_recorded_on_cancel_and_complete(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()

    server.complete_job(job.job_id)
    db.flush()

    event_types = [e.event_type for e in job.events]
    assert event_types == [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED]


def test_get_job_events_returns_chronological_history(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    server.complete_job(job.job_id)
    db.flush()

    events = server.get_job_events(job.job_id)
    assert [e.event_type for e in events] == [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.COMPLETED]
    assert all(e.comment for e in events)


def test_get_job_events_rejects_unknown_job(db):
    server = Server(db)
    with pytest.raises(JobNotFoundError):
        server.get_job_events(999999)


def test_get_job_returns_the_job(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()

    fetched = server.get_job(job.job_id)
    assert fetched.job_id == job.job_id


def test_list_institutes_and_get_institute(db, seeded_cluster):
    server = Server(db)
    institutes = server.list_institutes()
    assert seeded_cluster["institute_id"] in [i.institute_id for i in institutes]

    institute = server.get_institute(seeded_cluster["institute_id"])
    assert institute.institute_id == seeded_cluster["institute_id"]

    with pytest.raises(InstituteNotFoundError):
        server.get_institute(999999)


def test_list_clients_filters_by_institute_and_get_client(db, seeded_cluster):
    server = Server(db)
    clients = server.list_clients(institute_id=seeded_cluster["institute_id"])
    assert seeded_cluster["client_id"] in [c.client_id for c in clients]

    client = server.get_client(seeded_cluster["client_id"])
    assert client.client_id == seeded_cluster["client_id"]

    with pytest.raises(ClientNotFoundError):
        server.get_client(999999)


def test_delete_quota_removes_it(db, seeded_cluster):
    server = Server(db)
    quota = server.create_quota(institute_id=seeded_cluster["institute_id"], resource_type=ResourceType.CPU, limit=4)

    server.delete_quota(quota.id)

    assert db.query(models.Quota).filter_by(id=quota.id).one_or_none() is None


def test_delete_quota_rejects_unknown_quota(db):
    server = Server(db)
    with pytest.raises(QuotaNotFoundError):
        server.delete_quota(999999)


def test_cancel_reservation_removes_it_and_its_node_reservations(db, seeded_cluster):
    server = Server(db)
    reservation = server.create_reservation(
        institute_id=seeded_cluster["institute_id"],
        cluster_id=seeded_cluster["cluster_id"],
        node_ids=[seeded_cluster["nodes"][0].node_id],
        start_period=datetime.now(timezone.utc),
        end_period=datetime.now(timezone.utc) + timedelta(hours=1),
        reason="test",
    )

    server.cancel_reservation(reservation.id)

    assert db.query(models.Reservation).filter_by(id=reservation.id).one_or_none() is None
    assert db.query(models.NodeReservation).filter_by(reservation_id=reservation.id).all() == []


def test_cancel_reservation_rejects_unknown_reservation(db):
    server = Server(db)
    with pytest.raises(ReservationNotFoundError):
        server.cancel_reservation(999999)


def test_cancelled_reservation_no_longer_blocks_other_institutes(db):
    reserving_institute, _ = create_institute_and_client(db, owner="owner")
    other_institute, other_client = create_institute_and_client(db, owner="other", institute_name="Other Institute")
    cluster, nodes = create_cluster_with_nodes(db, node_count=1, resources_per_node=2)

    server = Server(db)
    reservation = server.create_reservation(
        institute_id=reserving_institute.institute_id,
        cluster_id=cluster.cluster_id,
        node_ids=[nodes[0].node_id],
        start_period=datetime.now(timezone.utc) - timedelta(hours=1),
        end_period=datetime.now(timezone.utc) + timedelta(hours=1),
        reason="test",
    )

    server.cancel_reservation(reservation.id)

    job = server.submit_job(
        client_id=other_client.client_id, requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    assert job.status == JobStatus.RUNNING


def test_set_node_down_rejects_unknown_node(db):
    server = Server(db)
    with pytest.raises(NodeNotFoundError):
        server.set_node_down(999999)


def test_set_node_down_marks_available_resources_unavailable(db, seeded_cluster):
    server = Server(db)
    node = seeded_cluster["nodes"][0]

    server.set_node_down(node.node_id)
    db.expire_all()

    refreshed = db.query(models.Node).filter_by(node_id=node.node_id).one()
    assert refreshed.status == NodeStatus.DOWN
    assert all(r.resource_status == ResourceStatus.UNAVAILABLE for r in refreshed.resources)


def test_set_node_down_waits_for_running_job_then_marks_it_unavailable(db, seeded_cluster):
    server = Server(db)
    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 2)], priority=Priority.NORMAL, duration=10
    )
    db.flush()
    allocation = server.get_allocation_details(job.job_id)
    resource_ids = [an.resource_node_id for an in allocation.allocation_nodes]
    used_node_id = db.query(models.ResourceNode).filter_by(resource_node_id=resource_ids[0]).one().node_id

    server.set_node_down(used_node_id)
    db.expire_all()

    # Still running -- decommissioning waits, doesn't evict.
    allocated = db.query(models.ResourceNode).filter(models.ResourceNode.resource_node_id.in_(resource_ids)).all()
    assert all(r.resource_status == ResourceStatus.ALLOCATED for r in allocated)
    assert job.status == JobStatus.RUNNING

    server.complete_job(job.job_id)
    db.expire_all()

    released = db.query(models.ResourceNode).filter(models.ResourceNode.resource_node_id.in_(resource_ids)).all()
    assert all(r.resource_status == ResourceStatus.UNAVAILABLE for r in released)  # not AVAILABLE


def test_placement_skips_a_down_node(db, seeded_cluster):
    server = Server(db)
    server.set_node_down(seeded_cluster["nodes"][0].node_id)  # -2 CPUs from the 8-capacity cluster

    job = server.submit_job(
        client_id=seeded_cluster["client_id"], requirements=[(ResourceType.CPU, 8)], priority=Priority.NORMAL, duration=10
    )
    # Fits the cluster's total (still 8) but not what's actually free (6) with a node down.
    assert job.status == JobStatus.QUEUED
