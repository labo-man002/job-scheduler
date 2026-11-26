"""Compare queue policies by replaying arrivals and releases in virtual time."""

from collections import deque
from dataclasses import dataclass, field
from heapq import heappop, heappush
from math import ceil
from statistics import mean, median

from app.domain.place_algorithm import PackAlgorithm
from app.domain.placer import Placer
from app.domain.sort_strategy import FifoSort, PrioritySort
from app.domain.topology import Topology
from app.enums import NodeStatus, Priority, ResourceStatus, ResourceType, TopologyType
from app.models import Cluster, Job, Node, ResourceNode, ResourceRequirement

from .replay_input import ReplayJob, Scenario

POLICIES = {"fifo": FifoSort, "priority": PrioritySort}


@dataclass(order=True)
class Completion:
    tick: int
    sequence: int
    job: ReplayJob = field(compare=False)
    resources: list[ResourceNode] = field(compare=False)


def make_placer(scenario: Scenario) -> Placer:
    cluster = Cluster(
        cluster_id=1,
        cluster_name="replay",
        topology_type=TopologyType.RING,
        dimension=[len(scenario.nodes)],
        wrap=False,
    )
    resource_id = 0
    for index, spec in enumerate(scenario.nodes):
        node = Node(node_id=spec.id, coordinates=[index], status=NodeStatus.IDLE)
        for unit in range(spec.gpus):
            resource_id += 1
            node.resources.append(
                ResourceNode(
                    resource_node_id=resource_id,
                    resource_type=ResourceType.GPU,
                    resource_type_index=unit,
                    resource_status=ResourceStatus.AVAILABLE,
                )
            )
        cluster.nodes.append(node)
    return Placer(list(cluster.nodes), PackAlgorithm(), Topology(cluster))


def make_job(spec: ReplayJob) -> Job:
    return Job(
        job_id=spec.id,
        priority=spec.priority,
        duration=spec.duration,
        client_id=1,
        requirements=[ResourceRequirement(resource_type=ResourceType.GPU, amount=spec.gpus)],
    )


def run_replay(scenario: Scenario, policy: str) -> dict:
    """Run one policy against independent inventory and return its event ledger."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown queue policy: {policy!r}")
    strategy = POLICIES[policy]()
    placer = make_placer(scenario)
    capacity = sum(node.gpus for node in scenario.nodes)
    arrivals = deque(sorted(scenario.jobs, key=lambda job: job.arrival))
    # The input schema describes a fully connected cluster of interchangeable
    # whole GPUs. Empty-cluster feasibility therefore depends only on count.
    impossible = {job.id for job in scenario.jobs if job.gpus > capacity}
    waiting: list[tuple[int, int, ReplayJob]] = []
    running: list[Completion] = []
    starts: dict[int, int] = {}
    events: list[dict] = []
    arrival_sequence = 0
    start_sequence = 0
    allocated = 0

    while arrivals or running:
        tick = arrivals[0].arrival if arrivals else running[0].tick
        if running:
            tick = min(tick, running[0].tick)

        while running and running[0].tick == tick:
            completed = heappop(running)
            placer.release_resource(completed.resources)
            allocated -= len(completed.resources)
            events.append({"tick": tick, "kind": "release", "job_id": completed.job.id})

        while arrivals and arrivals[0].arrival == tick:
            job = arrivals.popleft()
            if job.id in impossible:
                events.append({"tick": tick, "kind": "rejected", "job_id": job.id, "reason": "cannot_fit_empty_cluster"})
                continue
            events.append({"tick": tick, "kind": "arrival", "job_id": job.id})
            arrival_sequence += 1
            heappush(waiting, (strategy.key(job), arrival_sequence, job))

        # Keep a blocked job's original arrival position among jobs of equal rank.
        while waiting:
            _, _, job = waiting[0]
            resources = placer.place(make_job(job))
            if resources is None:
                events.append({"tick": tick, "kind": "blocked", "job_id": job.id, "free_gpus": capacity - allocated})
                break
            heappop(waiting)
            starts[job.id] = tick
            start_sequence += 1
            allocated += len(resources)
            heappush(running, Completion(tick + job.duration, start_sequence, job, resources))
            events.append(
                {
                    "tick": tick,
                    "kind": "start",
                    "job_id": job.id,
                    "gpus": [{"node_id": resource.node.node_id, "index": resource.resource_type_index} for resource in resources],
                }
            )

    outcomes = []
    for job in scenario.jobs:
        start = starts.get(job.id)
        if start is not None:
            outcome = {"status": "completed", "start": start, "finish": start + job.duration, "wait": start - job.arrival}
        else:
            reason = "cannot_fit_empty_cluster" if job.id in impossible else "no_future_dispatch_events"
            outcome = {"status": "unscheduled", "reason": reason}
        outcomes.append(
            {
                "id": job.id,
                "arrival": job.arrival,
                "duration": job.duration,
                "gpus": job.gpus,
                "priority": job.priority.value,
                **outcome,
            }
        )

    return {
        "policy": policy,
        "jobs": outcomes,
        "events": events,
        "metrics": summarize(outcomes, capacity, scenario.seconds_per_tick),
    }


def summarize(outcomes: list[dict], capacity: int, seconds_per_tick: int) -> dict:
    completed = [job for job in outcomes if job["status"] == "completed"]
    horizon = max((job["finish"] for job in completed), default=0)
    allocated_ticks = sum(job["gpus"] * job["duration"] for job in completed)
    available_ticks = capacity * horizon
    waits_by_priority = {}
    for priority in Priority:
        waits = sorted(job["wait"] for job in completed if job["priority"] == priority.value)
        if not waits:
            continue
        waits_by_priority[priority.value] = {
            "count": len(waits),
            "mean": mean(waits),
            "p50": median(waits) if len(waits) >= 5 else None,
            "p95": waits[ceil(0.95 * len(waits)) - 1] if len(waits) >= 20 else None,
        }

    return {
        "completed": len(completed),
        "unscheduled": len(outcomes) - len(completed),
        "makespan_ticks_from_zero": horizon,
        "completed_jobs_per_hour": len(completed) * 3600 / (horizon * seconds_per_tick) if horizon else None,
        "allocated_gpu_ticks": allocated_ticks,
        "available_gpu_ticks": available_ticks,
        "occupancy": allocated_ticks / available_ticks if available_ticks else None,
        "wait_ticks_by_priority": waits_by_priority,
    }
