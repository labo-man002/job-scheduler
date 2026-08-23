"""Custom business metrics, on top of prometheus-fastapi-instrumentator's
automatic HTTP request metrics (see app.main). Polled on an interval rather
than updated inline at every state change in Server -- these are gauges over
current state, and re-deriving them from the DB via existing Server methods
(cluster_fragmentation, list_queue) is simpler than threading metric updates
through every mutation path.
"""

import logging

from prometheus_client import Gauge
from sqlalchemy import func

from app import models
from app.database import SessionLocal
from app.domain.server import Server
from app.enums import JobStatus

logger = logging.getLogger(__name__)

_CLUSTER_LABELS = ["cluster_id", "cluster_name"]

CLUSTER_TOTAL_CAPACITY = Gauge("jobscheduler_cluster_total_capacity", "Total resource units in the cluster", _CLUSTER_LABELS)
CLUSTER_FREE_CAPACITY = Gauge("jobscheduler_cluster_free_capacity", "Free resource units in the cluster", _CLUSTER_LABELS)
CLUSTER_FRAGMENTATION = Gauge("jobscheduler_cluster_fragmentation", "Idle-capacity fragmentation ratio (0-1)", _CLUSTER_LABELS)
CLUSTER_QUEUE_DEPTH = Gauge("jobscheduler_queue_depth", "Jobs currently queued", _CLUSTER_LABELS)
JOBS_BY_STATUS = Gauge("jobscheduler_jobs_by_status", "Jobs grouped by status", ["status"])


def collect_once() -> None:
    db = SessionLocal()
    try:
        server = Server(db)
        for cluster in server.list_clusters():
            labels = {"cluster_id": str(cluster.cluster_id), "cluster_name": cluster.cluster_name}
            CLUSTER_TOTAL_CAPACITY.labels(**labels).set(cluster.total_capacity())
            CLUSTER_FREE_CAPACITY.labels(**labels).set(cluster.free_capacity())
            fragmentation, _, _ = server.cluster_fragmentation(cluster.cluster_id)
            CLUSTER_FRAGMENTATION.labels(**labels).set(fragmentation)
            CLUSTER_QUEUE_DEPTH.labels(**labels).set(len(server.list_queue(cluster.cluster_id)))

        counts = dict(db.query(models.Job.status, func.count(models.Job.job_id)).group_by(models.Job.status).all())
        for status in JobStatus:
            JOBS_BY_STATUS.labels(status=status.value).set(counts.get(status, 0))
    except Exception:
        logger.exception("metrics collection failed")
    finally:
        db.close()
