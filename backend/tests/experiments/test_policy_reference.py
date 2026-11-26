"""Cross-check the event-driven implementation with a tick-by-tick reference."""

from random import Random

import pytest

from app.experiments.replay import run_replay
from app.experiments.replay_input import Scenario


@pytest.mark.parametrize("policy", ["fifo", "priority"])
def test_seeded_workloads_match_tick_by_tick_reference(policy):
    ranks = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
    for seed in range(10):
        rng = Random(seed)
        jobs = [
            dict(id=i, arrival=rng.randrange(10), duration=rng.randint(1, 5),
                 gpus=rng.randint(1, 4), priority=rng.choice(list(ranks)))
            for i in range(1, 17)
        ]
        scenario = Scenario.model_validate(dict(
            schema_version=1, source=f"reference fixture {seed}", seconds_per_tick=1,
            nodes=[{"id": 10, "gpus": 2}, {"id": 20, "gpus": 2}], jobs=jobs,
        ))
        starts = {}
        pending = []
        active = []
        # Even serial execution must drain by the last arrival plus all service times.
        for tick in range(max(job["arrival"] for job in jobs) + sum(job["duration"] for job in jobs) + 1):
            active = [(finish, size) for finish, size in active if finish > tick]
            pending.extend(job for job in jobs if job["arrival"] == tick)
            if policy == "priority":
                pending.sort(key=lambda job: ranks[job["priority"]])
            free = 4 - sum(size for _, size in active)
            while pending and pending[0]["gpus"] <= free:
                job = pending.pop(0)
                starts[job["id"]] = tick
                active.append((tick + job["duration"], job["gpus"]))
                free -= job["gpus"]
        actual = run_replay(scenario, policy)
        assert {job["id"]: job["start"] for job in actual["jobs"]} == starts, seed
