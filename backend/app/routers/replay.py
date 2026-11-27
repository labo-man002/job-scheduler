"""Policy comparisons for the checked-in replay scenarios."""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.experiments.replay import run_replay
from app.experiments.replay_input import MAX_NODE_GPUS, PositiveInt, ReplayTopology, Scenario

router = APIRouter(prefix="/replay", tags=["replay"])
EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "queue-replay"


class JobComparison(BaseModel):
    id: int
    priority: str
    gpus: int
    fifo_wait: int | None
    priority_wait: int | None
    reason: str | None
    fifo_node_ids: list[int] | None = None
    priority_node_ids: list[int] | None = None
    fifo_leaf_ids: list[int] | None = None
    priority_leaf_ids: list[int] | None = None
    fifo_cross_leaf: bool | None = None
    priority_cross_leaf: bool | None = None


class PolicyMetrics(BaseModel):
    completed: int
    unscheduled: int
    makespan_ticks_from_zero: int
    completed_jobs_per_hour: float | None
    occupancy: float | None
    allocated_gpu_ticks: int
    available_gpu_ticks: int
    cross_leaf_placements: int | None = None


class Comparison(BaseModel):
    source: str
    seconds_per_tick: int
    fifo: PolicyMetrics
    priority: PolicyMetrics
    jobs: list[JobComparison]


ScenarioName = Literal["oracle", "contention"]
NodeCapacities = Annotated[list[Annotated[PositiveInt, Field(le=MAX_NODE_GPUS)]], Field(min_length=1, max_length=4)]


class ClusterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gpus_per_node: NodeCapacities
    topology: ReplayTopology | None = None


@router.get("/{scenario_name}", response_model=Comparison)
def compare(scenario_name: ScenarioName):
    return compare_cluster(scenario_name, None)


@router.post("/{scenario_name}", response_model=Comparison)
def compare_custom(scenario_name: ScenarioName, config: ClusterConfig):
    return compare_cluster(scenario_name, config)


def load_preset(scenario_name: ScenarioName) -> Scenario:
    return Scenario.model_validate_json((EXAMPLES / f"{scenario_name}.json").read_bytes())


def configure_scenario(
    scenario: Scenario, gpus_per_node: NodeCapacities | None, topology: ReplayTopology | None = None
) -> Scenario:
    effective = scenario.model_dump(exclude_none=True)
    if gpus_per_node is not None:
        ids = [node.id for node in scenario.nodes] if len(gpus_per_node) == len(scenario.nodes) else range(1, len(gpus_per_node) + 1)
        effective["nodes"] = [{"id": node_id, "gpus": count} for node_id, count in zip(ids, gpus_per_node, strict=True)]
    if topology is not None:
        effective["schema_version"] = 2
        effective["topology"] = topology.model_dump()
    return Scenario.model_validate(effective)


def compare_cluster(scenario_name: ScenarioName, config: ClusterConfig | None):
    scenario = load_preset(scenario_name)
    if config is not None:
        try:
            scenario = configure_scenario(scenario, config.gpus_per_node, config.topology)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors(include_url=False, include_context=False)) from error
    fifo, priority = (run_replay(scenario, policy) for policy in ("fifo", "priority"))
    return compare_outputs(scenario, fifo, priority)


def compare_outputs(scenario: Scenario, fifo: dict, priority: dict) -> Comparison:
    priority_jobs = {job["id"]: job for job in priority["jobs"]}
    jobs = []
    for job in fifo["jobs"]:
        alternative = priority_jobs[job["id"]]
        jobs.append(JobComparison(
            id=job["id"],
            priority=job["priority"],
            gpus=job["gpus"],
            fifo_wait=job.get("wait"),
            priority_wait=alternative.get("wait"),
            reason=job.get("reason"),
            fifo_node_ids=job.get("node_ids"),
            priority_node_ids=alternative.get("node_ids"),
            fifo_leaf_ids=job.get("leaf_ids"),
            priority_leaf_ids=alternative.get("leaf_ids"),
            fifo_cross_leaf=job.get("cross_leaf"),
            priority_cross_leaf=alternative.get("cross_leaf"),
        ))
    return Comparison(
        source=scenario.source,
        seconds_per_tick=scenario.seconds_per_tick,
        fifo=PolicyMetrics.model_validate(fifo["metrics"]),
        priority=PolicyMetrics.model_validate(priority["metrics"]),
        jobs=jobs,
    )
