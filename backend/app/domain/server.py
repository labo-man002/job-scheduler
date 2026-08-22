"""Server: the boundary a Client talks to. Owns the DB session for the
duration of a call and is the only thing that reads/writes Allocation rows
(no separate AllocationRepository -- see docs/decisions.md for why).

Multi-cluster: a Job never specifies a cluster -- Server routes it to the
smallest cluster whose total capacity could fit it (best-fit), the same way
Placer already picks a node without the job knowing. That routing decision
is never persisted on Job either; it's recomputed deterministically (job
size + current cluster capacities) both at submission and, after a process
restart, when a cluster's Scheduler is first re-seeded from the DB.

Each cluster gets its own Scheduler (Server._schedulers, keyed by
cluster_id), one per process, so a job stuck waiting on one cluster never
blocks a different job on a different cluster. Scheduler only ever holds
PendingJob (app/domain/scheduler.py), never a live ORM Job: each request
gets its own session (FastAPI's get_db()), so a Job loaded in one request's
session would be detached garbage by the next. Cancelling a queued job
doesn't remove its ref from the heap -- _drain_queue() lazily discards it
if its DB status isn't QUEUED anymore once dequeued (the standard heapq
pattern for entries that can go stale). Placer, in contrast, is rebuilt
fresh on every drain: it must hold this transaction's row-locked
Node/ResourceNode objects.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

from app import models
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
from app.domain.place_algorithm import PackAlgorithm
from app.domain.placer import Placer
from app.domain.scheduler import PendingJob, Scheduler
from app.domain.sort_strategy import PrioritySort
from app.domain.topology import Topology
from app.enums import (
    AllocationStatus,
    ClientStatus,
    JobStatus,
    NodeStatus,
    ResourceStatus,
    ResourceType,
    TopologyType,
)

logger = logging.getLogger(__name__)


@dataclass
class ResourceCount:
    resource_type: ResourceType
    count: int


@dataclass
class NodeSpec:
    coordinates: list[int]
    resources: list[ResourceCount]


_TOPOLOGY_AXES = {
    TopologyType.RING: 1,
    TopologyType.TORUS_2D: 2,
    TopologyType.MESH_2D: 2,
    TopologyType.TORUS_3D: 3,
    # FAT_TREE has no coordinate-grid meaning yet -- deliberately absent,
    # _validate_cluster_shape rejects it outright below.
}


def _validate_cluster_shape(topology_type, dimension, wrap):
    if topology_type == TopologyType.FAT_TREE:
        raise ValueError("FAT_TREE clusters aren't supported yet -- no coordinate/dimension model exists for them")
    if any(axis_size < 1 for axis_size in dimension):
        raise ValueError("every dimension entry must be >= 1")
    expected_axes = _TOPOLOGY_AXES[topology_type]
    if len(dimension) != expected_axes:
        raise ValueError(f"{topology_type.value} needs a {expected_axes}-axis dimension, got {len(dimension)}")
    if topology_type == TopologyType.MESH_2D and wrap:
        raise ValueError("MESH_2D cannot have wrap=True")  # a torus can go either way; a mesh, by definition, doesn't wrap


def _month_bounds(reference: datetime) -> tuple[datetime, datetime]:
    """[start, end) for the calendar month reference falls in, in reference's own tz."""
    start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, end


class Server:
    _schedulers: ClassVar[dict] = {}  # cluster_id -> Scheduler, one per process per cluster

    def __init__(self, db, sort_strategy=None, place_algorithm=None):
        self.db = db
        self.sort_strategy = sort_strategy or PrioritySort()
        self.place_algorithm = place_algorithm or PackAlgorithm()

    def register_client(self, owner, institute_id):
        if self.db.query(models.Institute).filter_by(institute_id=institute_id).one_or_none() is None:
            raise InstituteNotFoundError(institute_id)

        client = models.Client(owner=owner, institute_id=institute_id)  # client_status defaults to OFFLINE
        self.db.add(client)
        self.db.flush()
        logger.info("client %s registered (institute=%s, owner=%r)", client.client_id, institute_id, owner)
        return client

    def register_institute(self, institute_name):
        institute = models.Institute(institute_name=institute_name)
        self.db.add(institute)
        self.db.flush()
        logger.info("institute %s registered (%r)", institute.institute_id, institute_name)
        return institute

    def create_cluster(self, cluster_name, topology_type, dimension, wrap, node_specs: list[NodeSpec]):
        _validate_cluster_shape(topology_type, dimension, wrap)

        cluster = models.Cluster(cluster_name=cluster_name, topology_type=topology_type, dimension=dimension, wrap=wrap)
        self.db.add(cluster)
        self.db.flush()
        for spec in node_specs:
            node = models.Node(cluster=cluster, coordinates=spec.coordinates)  # cluster set first: coordinate validation needs it
            self.db.add(node)
            self.db.flush()
            for resource_count in spec.resources:
                for index in range(resource_count.count):
                    self.db.add(models.ResourceNode(
                        node_id=node.node_id, resource_type=resource_count.resource_type, resource_type_index=index
                    ))
        self.db.flush()
        logger.info("cluster %s created (%r, %d nodes)", cluster.cluster_id, cluster_name, len(node_specs))
        return cluster

    def create_quota(self, institute_id, resource_type, limit, period=None):
        """period: which calendar month this limit applies to (defaults to the
        current month)."""
        institute = self.db.query(models.Institute).filter_by(institute_id=institute_id).with_for_update().one_or_none()
        if institute is None:
            raise InstituteNotFoundError(institute_id)

        period = period or datetime.now(timezone.utc)
        month_start, month_end = _month_bounds(period)

        quota = (
            self.db.query(models.Quota)
            .filter(models.Quota.institute_id == institute_id)
            .filter(models.Quota.resource_type == resource_type)
            .filter(models.Quota.period >= month_start)
            .filter(models.Quota.period < month_end)
            .one_or_none()
        )
        if quota is None:
            quota = models.Quota(institute_id=institute_id, resource_type=resource_type, limit=limit, period=period)
            self.db.add(quota)
        else:
            quota.limit = limit
        self.db.flush()
        logger.info(
            "quota set: institute=%s resource_type=%s limit=%s month=%s",
            institute_id, resource_type, limit, month_start.date(),
        )
        return quota

    def create_reservation(self, institute_id, cluster_id, node_ids, start_period, end_period, reason):
        """Doesn't touch any currently-RUNNING allocation on these nodes, even
        one belonging to a different institute -- the reservation only governs
        future placement decisions."""
        if self.db.query(models.Institute).filter_by(institute_id=institute_id).one_or_none() is None:
            raise InstituteNotFoundError(institute_id)
        if self.db.query(models.Cluster).filter_by(cluster_id=cluster_id).one_or_none() is None:
            raise ClusterNotFoundError(cluster_id)

        # Lock the target nodes preventing  the same double-booking
        nodes = self.db.query(models.Node).filter(models.Node.node_id.in_(node_ids)).with_for_update().all()
        if len(nodes) != len(set(node_ids)):
            raise NodeNotFoundError(node_ids)
        wrong_cluster = [node.node_id for node in nodes if node.cluster_id != cluster_id]
        if wrong_cluster:
            raise NodeNotInClusterError(wrong_cluster, cluster_id)

        conflicting = (
            self.db.query(models.NodeReservation)
            .join(models.Reservation)
            .filter(models.NodeReservation.node_id.in_(node_ids))
            .filter(models.Reservation.institute_id != institute_id)
            .filter(models.Reservation.start_period < end_period)
            .filter(models.Reservation.end_period > start_period)
            .all()
        )
        if conflicting:
            raise ReservationConflictError(sorted({row.node_id for row in conflicting}))

        reservation = models.Reservation(
            institute_id=institute_id, start_period=start_period, end_period=end_period, reason=reason
        )
        self.db.add(reservation)
        self.db.flush()
        for node in nodes:
            self.db.add(models.NodeReservation(node_id=node.node_id, reservation_id=reservation.id))
        self.db.flush()
        logger.info("reservation %s created: institute=%s nodes=%s", reservation.id, institute_id, node_ids)
        return reservation

    def list_reservations(self, institute_id=None, cluster_id=None):
        query = self.db.query(models.Reservation)
        if institute_id is not None:
            query = query.filter_by(institute_id=institute_id)
        if cluster_id is not None:
            # Reservation has no cluster_id column of its own -- join through its
            # nodes (every node in a reservation shares one cluster, enforced at
            # creation) to filter by it.
            query = (
                query.join(models.NodeReservation, models.NodeReservation.reservation_id == models.Reservation.id)
                .join(models.Node, models.Node.node_id == models.NodeReservation.node_id)
                .filter(models.Node.cluster_id == cluster_id)
                .distinct()
            )
        return query.all()

    def cancel_reservation(self, reservation_id):
        """Doesn't touch any placement decision already made under this
        reservation's cover -- only removes it from future exclusion checks."""
        reservation = self.db.query(models.Reservation).filter_by(id=reservation_id).one_or_none()
        if reservation is None:
            raise ReservationNotFoundError(reservation_id)
        self.db.query(models.NodeReservation).filter_by(reservation_id=reservation_id).delete()
        self.db.delete(reservation)
        self.db.flush()
        logger.info("reservation %s cancelled", reservation_id)

    def list_quotas(self, institute_id=None):
        query = self.db.query(models.Quota)
        if institute_id is not None:
            query = query.filter_by(institute_id=institute_id)
        return query.all()

    def delete_quota(self, quota_id):
        quota = self.db.query(models.Quota).filter_by(id=quota_id).one_or_none()
        if quota is None:
            raise QuotaNotFoundError(quota_id)
        self.db.delete(quota)
        self.db.flush()
        logger.info("quota %s deleted", quota_id)

    def list_clusters(self):
        return self.db.query(models.Cluster).all()

    def get_cluster(self, cluster_id):
        cluster = self.db.query(models.Cluster).filter_by(cluster_id=cluster_id).one_or_none()
        if cluster is None:
            raise ClusterNotFoundError(cluster_id)
        return cluster

    def list_cluster_allocations(self, cluster_id):
        """Every currently-occupied resource unit in this cluster, and which job
        occupies it -- the reverse lookup of get_allocation_details (job -> nodes)."""
        return (
            self.db.query(models.AllocationNode)
            .join(models.ResourceNode, models.ResourceNode.resource_node_id == models.AllocationNode.resource_node_id)
            .join(models.Node, models.Node.node_id == models.ResourceNode.node_id)
            .join(models.Allocation, models.Allocation.allocation_id == models.AllocationNode.allocation_id)
            .filter(models.Node.cluster_id == cluster_id)
            .filter(models.Allocation.allocation_status == AllocationStatus.ALLOCATED)
            .all()
        )

    def set_node_down(self, node_id):
        """Decommission a node without evicting whatever's currently running
        on it"""
        node = self.db.query(models.Node).filter_by(node_id=node_id).with_for_update().one_or_none()
        if node is None:
            raise NodeNotFoundError(node_id)

        resources = self.db.query(models.ResourceNode).filter_by(node_id=node_id).with_for_update().all()
        node.status = NodeStatus.DOWN
        for resource in resources:
            if resource.resource_status == ResourceStatus.AVAILABLE:
                resource.resource_status = ResourceStatus.UNAVAILABLE
        self.db.flush()
        logger.info("node %s marked DOWN", node_id)
        return node

    def list_institutes(self):
        return self.db.query(models.Institute).all()

    def get_institute(self, institute_id):
        institute = self.db.query(models.Institute).filter_by(institute_id=institute_id).one_or_none()
        if institute is None:
            raise InstituteNotFoundError(institute_id)
        return institute

    def list_clients(self, institute_id=None):
        query = self.db.query(models.Client)
        if institute_id is not None:
            query = query.filter_by(institute_id=institute_id)
        return query.order_by(models.Client.client_id).all()

    def get_client(self, client_id):
        client = self.db.query(models.Client).filter_by(client_id=client_id).one_or_none()
        if client is None:
            raise ClientNotFoundError(client_id)
        return client

    def list_jobs(self, client_id=None, status=None):
        query = self.db.query(models.Job)
        if client_id is not None:
            query = query.filter_by(client_id=client_id)
        if status is not None:
            query = query.filter_by(status=status)
        return query.order_by(models.Job.job_id).all()

    def get_job(self, job_id):
        return self._get_job_or_raise(job_id)

    def get_job_events(self, job_id):
        job = self._get_job_or_raise(job_id)
        return sorted(job.events, key=lambda event: event.id)

    def list_recent_events(self, limit=20):
        # Order by id, not just time -- two events from the same submit_job call (e.g.
        # QUEUED immediately followed by RUNNING placement) can share an identical
        # timestamp, and id reflects true insertion order as a tiebreaker.
        return self.db.query(models.JobEvent).order_by(models.JobEvent.id.desc()).limit(limit).all()

    def submit_job(self, client_id, requirements, priority, duration):
        """requirements: list of (ResourceType, amount). `duration` is the
        client's estimate, not a commitment."""
        resource_types = [resource_type for resource_type, _ in requirements]
        if len(resource_types) != len(set(resource_types)):
            # Placer.place() keys its "needed" dict by resource_type (app/domain/placer.py) --
            raise ValueError("requirements can't repeat the same resource_type -- combine into a single amount instead")

        client = self.db.query(models.Client).filter_by(client_id=client_id).one_or_none()
        if client is None:
            raise ClientNotFoundError(client_id)
        client.client_status = ClientStatus.ONLINE  # last-activity marker, not true liveness -- see docs/decisions.md
        self._check_quota(client.institute_id, requirements)

        job_size = sum(amount for _, amount in requirements)
        cluster = self._best_fit_cluster(job_size)  # raises JobTooLargeError if nothing ever could fit
        # Fetch (and, on first use, seed) the scheduler before this job exists in the
        # DB as QUEUED -- otherwise seeding would pick it up too, then it gets
        # enqueued a second time below.
        scheduler = self._get_scheduler(cluster.cluster_id)

        job = models.Job(client_id=client_id, priority=priority, duration=duration, status=JobStatus.QUEUED)
        self.db.add(job)
        self.db.flush()
        for resource_type, amount in requirements:
            self.db.add(models.ResourceRequirement(job_id=job.job_id, resource_type=resource_type, amount=amount))
        self._record_event(job, JobStatus.QUEUED, f"Submitted, routed to cluster {cluster.cluster_id}")
        self.db.flush()
        scheduler.enqueue(PendingJob(job.job_id, job.priority))
        self._drain_queue(cluster.cluster_id, scheduler)
        logger.info("job %s %s (client=%s, cluster=%s)", job.job_id, job.status.value, client_id, cluster.cluster_id)
        return job

    def cancel_job(self, job_id):
        job = self._get_job_or_raise(job_id)
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            self._record_event(job, JobStatus.CANCELLED, "Cancelled while queued")
        elif job.status == JobStatus.RUNNING:
            self._end_running_job(job, JobStatus.CANCELLED)
        self.db.flush()
        logger.info("job %s cancelled", job_id)

    def complete_job(self, job_id):
        """A job reporting it finished on its own, as opposed to being cancelled."""
        job = self._get_job_or_raise(job_id)
        if job.status != JobStatus.RUNNING:
            raise JobNotRunningError(job_id)
        self._end_running_job(job, JobStatus.COMPLETED)
        self.db.flush()
        logger.info("job %s completed", job_id)

    def get_allocation_details(self, job_id):
        return self.db.query(models.Allocation).filter_by(job_id=job_id).one_or_none()

    def _get_job_or_raise(self, job_id):
        job = self.db.query(models.Job).filter_by(job_id=job_id).one_or_none()
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def _record_event(self, job, event_type, comment):
        self.db.add(models.JobEvent(job_id=job.job_id, event_type=event_type, comment=comment))

    def _check_quota(self, institute_id, requirements):
        """Quota is a live concurrency cap: how much of a resource_type an
        institute may have RUNNING at once. The limit itself is per calendar
        month (Quota.period) -- an institute can have a different limit each
        month, so this looks up whichever row's period falls in the current
        month, not just any row for institute+resource_type. No row for the
        current month means unrestricted, same as no Quota row at all."""
        month_start, month_end = _month_bounds(datetime.now(timezone.utc))
        for resource_type, amount in requirements:
            quota = (
                self.db.query(models.Quota)
                .filter(models.Quota.institute_id == institute_id)
                .filter(models.Quota.resource_type == resource_type)
                .filter(models.Quota.period >= month_start)
                .filter(models.Quota.period < month_end)
                .one_or_none()
            )
            if quota is None:
                continue

            currently_allocated = (
                self.db.query(models.AllocationNode)
                .join(models.ResourceNode, models.AllocationNode.resource_node_id == models.ResourceNode.resource_node_id)
                .join(models.Allocation, models.AllocationNode.allocation_id == models.Allocation.allocation_id)
                .join(models.Job, models.Allocation.job_id == models.Job.job_id)
                .join(models.Client, models.Job.client_id == models.Client.client_id)
                .filter(models.Client.institute_id == institute_id)
                .filter(models.Job.status == JobStatus.RUNNING)
                .filter(models.ResourceNode.resource_type == resource_type)
                .count()
            )
            if currently_allocated + amount > quota.limit:
                logger.warning(
                    "job submission rejected: institute %s quota exceeded for %s (limit=%s)",
                    institute_id, resource_type, quota.limit,
                )
                raise QuotaExceededError(resource_type, quota.limit)

    def _cluster_capacity(self, cluster_id):
        return (
            self.db.query(models.ResourceNode)
            .join(models.Node)
            .filter(models.Node.cluster_id == cluster_id)
            .count()
        )

    def _best_fit_cluster(self, job_size):
        clusters = self.db.query(models.Cluster).all()
        if not clusters:
            raise RuntimeError("No cluster configured")

        by_capacity = sorted(
            ((cluster, self._cluster_capacity(cluster.cluster_id)) for cluster in clusters),
            key=lambda pair: pair[1],
        )
        for cluster, capacity in by_capacity:
            if capacity >= job_size:
                return cluster
        logger.warning("job submission rejected: %s units requested, no cluster could ever fit it", job_size)
        raise JobTooLargeError(job_size)

    def _get_scheduler(self, cluster_id):
        if cluster_id not in Server._schedulers:
            scheduler = Scheduler(placer=None, sort_strategy=self.sort_strategy)
            for job in self.db.query(models.Job).filter_by(status=JobStatus.QUEUED).all():
                job_size = sum(r.amount for r in job.requirements)
                try:
                    best = self._best_fit_cluster(job_size)
                except JobTooLargeError:
                    continue  # shouldn't happen for an already-accepted job; don't crash cold-start over it
                if best.cluster_id == cluster_id:
                    scheduler.enqueue(PendingJob(job.job_id, job.priority))
            Server._schedulers[cluster_id] = scheduler
        return Server._schedulers[cluster_id]

    def _end_running_job(self, job, final_status):
        """Free a RUNNING job's resources and mark it done -- shared by
        cancellation and natural completion. Either way, only now do we
        actually know how long it ran, so end_time/duration are set here,
        not at placement time (see docs/decisions.md)."""
        allocation = self.db.query(models.Allocation).filter_by(job_id=job.job_id).one_or_none()
        cluster_id = None
        if allocation is not None:
            resource_nodes = [an.resource_node for an in allocation.allocation_nodes]
            if resource_nodes:
                cluster_id = resource_nodes[0].node.cluster_id
            self._build_placer(cluster_id).release_resource(resource_nodes)
            allocation.end_time = datetime.now(timezone.utc)
            allocation.duration = int((allocation.end_time - allocation.begin_time).total_seconds() // 60)
            allocation.allocation_status = AllocationStatus.RELEASED
        job.status = final_status
        self._record_event(job, final_status, "Cancelled while running" if final_status == JobStatus.CANCELLED else "Completed")
        if cluster_id is not None:
            self._drain_queue(cluster_id, self._get_scheduler(cluster_id))  # freed resources may unblock others

    def _build_placer(self, cluster_id):
        cluster = self.db.query(models.Cluster).filter_by(cluster_id=cluster_id).one_or_none()
        if cluster is None:
            raise RuntimeError(f"Cluster {cluster_id} not found")

        nodes = (
            self.db.query(models.Node)
            .filter_by(cluster_id=cluster_id)
            .with_for_update()
            .all()
        )
        # Lock the actual contended rows (ResourceNode.resource_status) so a
        # concurrent request can't read/allocate the same unit before this
        # transaction commits. Same session identity map, so node.resources
        # below refers to these same locked instances.
        node_ids = [node.node_id for node in nodes]
        self.db.query(models.ResourceNode).filter(
            models.ResourceNode.node_id.in_(node_ids)
        ).with_for_update().all()

        return Placer(nodes, self.place_algorithm, Topology(cluster))

    def _reserved_node_ids(self, cluster_id, exclude_institute_id):
        """Nodes reserved by a DIFFERENT institute, right now. Placer itself
        stays institute-agnostic -- Server narrows the candidate node list
        per job instead, since two queued jobs from different institutes can
        have different reservation rights on the very same cluster."""
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(models.NodeReservation)
            .join(models.Reservation)
            .join(models.Node, models.NodeReservation.node_id == models.Node.node_id)
            .filter(models.Node.cluster_id == cluster_id)
            .filter(models.Reservation.start_period <= now)
            .filter(models.Reservation.end_period > now)
            .filter(models.Reservation.institute_id != exclude_institute_id)
            .all()
        )
        return {row.node_id for row in rows}

    def _drain_queue(self, cluster_id, scheduler):
        placer = None  # only build it (and take the locks) if there's actually something to try
        all_nodes = None
        skipped = []  # reservation-only failures, held aside so they aren't re-dequeued this same pass

        while (ref := scheduler.dequeue()) is not None:
            job = self.db.query(models.Job).filter_by(job_id=ref.job_id).one_or_none()
            if job is None or job.status != JobStatus.QUEUED:
                # Went stale since it was enqueued (e.g. cancelled while queued) --
                # lazy deletion, see the module docstring. Not a placement failure,
                # so it doesn't stop the drain.
                continue

            if placer is None:
                placer = self._build_placer(cluster_id)
                all_nodes = placer.nodes
                scheduler.placer = placer

            excluded = self._reserved_node_ids(cluster_id, job.client.institute_id)
            placer.nodes = [n for n in all_nodes if n.node_id not in excluded]

            reserved = scheduler.attempt_placement(job)
            if not reserved:
                if excluded and placer.has_enough_capacity(job, all_nodes):
                    # It only failed because reservation exclusion narrowed its
                    # own institute's view of the cluster -- not because the
                    # cluster is actually full. That's not the resource
                    # contention strict-order exists to protect (see below), so
                    # it doesn't get to stall every other institute's jobs.
                    # Held aside, not re-enqueued yet: putting it straight back
                    # would just have us dequeue this same ref again next.
                    skipped.append(ref)
                    continue
                # Strict order: don't skip ahead to a lower-priority job just
                # because the head of the queue didn't fit. That's backfilling
                # -- an explicit, opt-in relaxation of this, not the default.
                # Put it back: it's still queued, just not placed this round.
                scheduler.enqueue(ref)
                break

            allocation = models.Allocation(job_id=job.job_id, allocation_status=AllocationStatus.ALLOCATED)
            self.db.add(allocation)
            self.db.flush()
            for resource_node in reserved:
                self.db.add(
                    models.AllocationNode(
                        allocation_id=allocation.allocation_id,
                        resource_node_id=resource_node.resource_node_id,
                    )
                )
            job.status = JobStatus.RUNNING
            self._record_event(job, JobStatus.RUNNING, f"Placed on {len(reserved)} resource unit(s)")
            self.db.flush()  # visible to a query later in this same call/session (e.g. a subsequent submit_job's quota check)

        for ref in skipped:
            scheduler.enqueue(ref)
