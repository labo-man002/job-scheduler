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
from app.enums import NodeStatus, OperationalState, Priority, ResourceStatus, ResourceType, TopologyType
from app.models import Cluster, Job, Node, ResourceNode, ResourceRequirement

from .replay_input import LeafSpineTopologyInput, ReplayJob, Scenario
from .replay_topology import LINK_CAPACITY_GBPS, make_leaf_spine

POLICIES = {"fifo": FifoSort, "priority": PrioritySort}


@dataclass(order=True)
class Completion:
    tick: int
    sequence: int
    job: ReplayJob = field(compare=False)
    resources: list[ResourceNode] = field(compare=False)


@dataclass(frozen=True)
class ReplayBoundary:
    tick: int
    running_starts: dict[int, int]


def make_placer(scenario: Scenario) -> Placer:
    fabric = isinstance(scenario.topology, LeafSpineTopologyInput)
    cluster = Cluster(
        cluster_id=1,
        cluster_name="replay",
        topology_type=TopologyType.LEAF_SPINE if fabric else TopologyType.RING,
        dimension=[] if fabric else [len(scenario.nodes)],
        wrap=False,
    )
    resource_id = 0
    for index, spec in enumerate(scenario.nodes):
        node = Node(node_id=spec.id, coordinates=[index], status=NodeStatus.IDLE)
        if fabric:
            node.nic_capacity_gbps = LINK_CAPACITY_GBPS
            node.nic_state = OperationalState.UP
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
    nodes = list(cluster.nodes)
    topology = (
        make_leaf_spine(scenario.topology, nodes)
        if isinstance(scenario.topology, LeafSpineTopologyInput)
        else Topology(cluster)
    )
    return Placer(nodes, PackAlgorithm(), topology)


def make_job(spec: ReplayJob) -> Job:
    return Job(
        job_id=spec.id,
        priority=spec.priority,
        duration=spec.duration,
        client_id=1,
        requirements=[ResourceRequirement(resource_type=ResourceType.GPU, amount=spec.gpus)],
    )


def run_replay(scenario: Scenario, policy: str, *, boundary: ReplayBoundary | None = None) -> dict:
    """Run one policy against independent inventory and return its event ledger."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown queue policy: {policy!r}")
    strategy = POLICIES[policy]()
    placer = make_placer(scenario)
    capacity = sum(node.gpus for node in scenario.nodes)
    arrivals = deque(sorted(scenario.jobs, key=lambda job: job.arrival))
    fabric = isinstance(scenario.topology, LeafSpineTopologyInput)
    leaf_by_node = {link.node: link.leaf for link in scenario.topology.attachments} if fabric else {}
    infeasible_demands = {}
    checked_demands = set()
    # In the fabric, the same number of GPUs can be split across components.
    # Every job requests only whole, interchangeable GPUs, so check each
    # distinct demand once against the empty cluster.
    for job in scenario.jobs:
        if job.gpus in checked_demands:
            continue
        checked_demands.add(job.gpus)
        if job.gpus > capacity:
            infeasible_demands[job.gpus] = "cannot_fit_empty_cluster"
        elif fabric and not placer.can_place(make_job(job)):
            infeasible_demands[job.gpus] = "no_connected_allocation"
    waiting: list[tuple[int, int, ReplayJob]] = []
    running: list[Completion] = []
    starts: dict[int, dict] = {}
    events: list[dict] = []
    arrival_sequence = 0
    start_sequence = 0
    allocated = 0

    def outcome_for(job: ReplayJob, start: int, resources: list[ResourceNode]) -> dict:
        node_ids = sorted({resource.node.node_id for resource in resources})
        leaf_ids = sorted({leaf_by_node[node_id] for node_id in node_ids}) if fabric else []
        return {
            "status": "completed",
            "start": start,
            "finish": start + job.duration,
            "wait": start - job.arrival,
            "node_ids": node_ids,
            "leaf_ids": leaf_ids,
            "cross_leaf": len(leaf_ids) > 1 if fabric else None,
        }

    boundary_tick = None
    if boundary is not None:
        by_id = {job.id: job for job in scenario.jobs}
        if boundary.tick < 0 or boundary.running_starts.keys() - by_id.keys():
            raise ValueError("Invalid replay boundary tick or running job IDs")
        boundary_tick = boundary.tick
        for job_id, start in sorted(boundary.running_starts.items(), key=lambda pair: (pair[1], pair[0])):
            job = by_id[job_id]
            if not job.arrival <= start < boundary_tick < start + job.duration:
                raise ValueError(f"Job {job_id} does not span the replay boundary")
            resources = placer.place(make_job(job))
            if resources is None:
                raise ValueError(f"Boundary jobs exceed replay capacity at job {job_id}")
            starts[job_id] = outcome_for(job, start, resources)
            start_sequence += 1
            allocated += len(resources)
            heappush(running, Completion(start + job.duration, start_sequence, job, resources))
            events.append({"tick": boundary_tick, "kind": "carry_in_running", "job_id": job_id})

    while boundary_tick is not None or arrivals or running:
        if boundary_tick is not None:
            tick = boundary_tick
            boundary_tick = None
        else:
            tick = arrivals[0].arrival if arrivals else running[0].tick
            if running:
                tick = min(tick, running[0].tick)

        while running and running[0].tick == tick:
            completed = heappop(running)
            placer.release_resource(completed.resources)
            allocated -= len(completed.resources)
            events.append({"tick": tick, "kind": "release", "job_id": completed.job.id})

        while arrivals and arrivals[0].arrival <= tick:
            job = arrivals.popleft()
            if job.id in starts:
                continue
            if reason := infeasible_demands.get(job.gpus):
                events.append({"tick": tick, "kind": "rejected", "job_id": job.id, "reason": reason})
                continue
            kind = "carry_in_waiting" if job.arrival < tick else "arrival"
            events.append({"tick": tick, "kind": kind, "job_id": job.id})
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
            starts[job.id] = outcome_for(job, tick, resources)
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
        outcome = starts.get(job.id)
        if outcome is None:
            outcome = {
                "status": "unscheduled",
                "reason": infeasible_demands.get(job.gpus, "no_future_dispatch_events"),
            }
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
        "metrics": {
            **summarize(outcomes, capacity, scenario.seconds_per_tick),
            "cross_leaf_placements": sum(job["cross_leaf"] for job in starts.values()) if fabric else None,
        },
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
