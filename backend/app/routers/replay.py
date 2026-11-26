"""Policy comparisons for the checked-in replay scenarios."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.experiments.replay import run_replay
from app.experiments.replay_input import Scenario

router = APIRouter(prefix="/replay", tags=["replay"])
EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "queue-replay"


class JobComparison(BaseModel):
    id: int
    priority: str
    gpus: int
    fifo_wait: int | None
    priority_wait: int | None
    reason: str | None


class PolicyMetrics(BaseModel):
    completed: int
    unscheduled: int
    makespan_ticks_from_zero: int
    completed_jobs_per_hour: float | None
    occupancy: float | None


class Comparison(BaseModel):
    source: str
    seconds_per_tick: int
    fifo: PolicyMetrics
    priority: PolicyMetrics
    jobs: list[JobComparison]


@router.get("/{scenario_name}", response_model=Comparison)
def compare(scenario_name: Literal["oracle", "contention"]):
    scenario = Scenario.model_validate_json((EXAMPLES / f"{scenario_name}.json").read_bytes())
    fifo, priority = (run_replay(scenario, policy) for policy in ("fifo", "priority"))
    priority_jobs = {job["id"]: job for job in priority["jobs"]}
    return {
        "source": scenario.source,
        "seconds_per_tick": scenario.seconds_per_tick,
        "fifo": fifo["metrics"],
        "priority": priority["metrics"],
        "jobs": [
            {
                "id": job["id"], "priority": job["priority"], "gpus": job["gpus"],
                "fifo_wait": job.get("wait"), "priority_wait": priority_jobs[job["id"]].get("wait"),
                "reason": job.get("reason"),
            }
            for job in fifo["jobs"]
        ],
    }
