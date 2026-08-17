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

from datetime import datetime, timezone

from app import models
from app.domain.place_algorithm import PackAlgorithm
from app.domain.placer import Placer
from app.domain.scheduler import PendingJob, Scheduler
from app.domain.sort_strategy import PrioritySort
from app.domain.topology import Topology
from app.enums import AllocationStatus, JobStatus


class ClientNotFoundError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class JobNotRunningError(Exception):
    pass


class JobTooLargeError(Exception):
    """No cluster, even fully empty, has enough capacity for this job --
    a rejection, not something waiting would ever resolve."""


class Server:
    _schedulers = {}  # cluster_id -> Scheduler, one per process per cluster

    def __init__(self, db, sort_strategy=None, place_algorithm=None):
        self.db = db
        self.sort_strategy = sort_strategy or PrioritySort()
        self.place_algorithm = place_algorithm or PackAlgorithm()

    def submit_job(self, client_id, requirements, priority, duration):
        """requirements: list of (ResourceType, amount). `duration` is the
        client's estimate, not a commitment."""
        if self.db.query(models.Client).filter_by(client_id=client_id).one_or_none() is None:
            raise ClientNotFoundError(client_id)

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
        self.db.flush()
        scheduler.enqueue(PendingJob(job.job_id, job.priority))
        self._drain_queue(cluster.cluster_id, scheduler)
        return job

    def cancel_job(self, job_id):
        job = self._get_job_or_raise(job_id)
        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
        elif job.status == JobStatus.RUNNING:
            self._end_running_job(job, JobStatus.CANCELLED)
        self.db.flush()

    def complete_job(self, job_id):
        """A job reporting it finished on its own, as opposed to being cancelled."""
        job = self._get_job_or_raise(job_id)
        if job.status != JobStatus.RUNNING:
            raise JobNotRunningError(job_id)
        self._end_running_job(job, JobStatus.COMPLETED)
        self.db.flush()

    def get_allocation_details(self, job_id):
        return self.db.query(models.Allocation).filter_by(job_id=job_id).one_or_none()

    def _get_job_or_raise(self, job_id):
        job = self.db.query(models.Job).filter_by(job_id=job_id).one_or_none()
        if job is None:
            raise JobNotFoundError(job_id)
        return job

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

    def _drain_queue(self, cluster_id, scheduler):
        placer = None  # only build it (and take the locks) if there's actually something to try

        while (ref := scheduler.dequeue()) is not None:
            job = self.db.query(models.Job).filter_by(job_id=ref.job_id).one_or_none()
            if job is None or job.status != JobStatus.QUEUED:
                # Went stale since it was enqueued (e.g. cancelled while queued) --
                # lazy deletion, see the module docstring. Not a placement failure,
                # so it doesn't stop the drain.
                continue

            if placer is None:
                placer = self._build_placer(cluster_id)
                scheduler.placer = placer

            reserved = scheduler.attempt_placement(job)
            if not reserved:
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
