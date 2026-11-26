import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.enums import Priority
from app.experiments.replay import run_replay
from app.experiments.replay_input import ReplayJob, Scenario

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples" / "queue-replay"


@pytest.fixture
def oracle():
    return Scenario.model_validate_json((EXAMPLES / "oracle.json").read_bytes())


def test_hand_calculated_policy_comparison(oracle):
    fifo = run_replay(oracle, "fifo")
    priority = run_replay(oracle, "priority")

    assert [job["wait"] for job in fifo["jobs"]] == [0, 4, 11]
    assert [job["wait"] for job in priority["jobs"]] == [0, 5, 3]
    for result in (fifo, priority):
        metrics = result["metrics"]
        assert metrics["makespan_ticks_from_zero"] == 14
        assert metrics["allocated_gpu_ticks"] == 27
        assert metrics["available_gpu_ticks"] == 28
        assert metrics["completed"] == 3
        assert metrics["wait_ticks_by_priority"]["HIGH"]["p95"] is None


def test_equal_priorities_give_identical_results_and_preserve_ties(oracle):
    equal_priority = oracle.model_copy(
        update={"jobs": tuple(job.model_copy(update={"priority": Priority.NORMAL}) for job in oracle.jobs)}
    )

    fifo = run_replay(equal_priority, "fifo")
    priority = run_replay(equal_priority, "priority")

    assert fifo["events"] == priority["events"]
    assert fifo["jobs"] == priority["jobs"]
    assert fifo["metrics"] == priority["metrics"]
    assert [event["job_id"] for event in priority["events"] if event["kind"] == "start"] == [1, 2, 3]


def test_releases_before_arrivals_and_dispatches_at_same_tick(oracle):
    same_tick = oracle.model_copy(
        update={"jobs": (*oracle.jobs[:2], oracle.jobs[2].model_copy(update={"arrival": 5}))}
    )

    tick_events = [event for event in run_replay(same_tick, "priority")["events"] if event["tick"] == 5]

    assert [(event["kind"], event["job_id"]) for event in tick_events] == [
        ("release", 1), ("arrival", 3), ("start", 3), ("blocked", 2)
    ]


def test_all_impossible_jobs_produce_empty_occupancy(oracle):
    impossible = oracle.model_copy(update={"jobs": (oracle.jobs[0].model_copy(update={"gpus": 3}),)})

    result = run_replay(impossible, "fifo")

    assert result["jobs"][0]["reason"] == "cannot_fit_empty_cluster"
    assert result["metrics"]["unscheduled"] == 1
    assert result["metrics"]["occupancy"] is None
    assert result["metrics"]["completed_jobs_per_hour"] is None


@pytest.mark.parametrize("policy", ["fifo", "priority"])
def test_multinode_ledger_matches_capacity_and_recovers_every_device(policy):
    scenario = Scenario.model_validate_json((EXAMPLES / "contention.json").read_bytes())
    result = run_replay(scenario, policy)
    demand = {job.id: job.gpus for job in scenario.jobs}
    capacity = {node.id: node.gpus for node in scenario.nodes}
    active = set()
    by_job = {}
    counts = Counter()

    for event in result["events"]:
        job_id = event["job_id"]
        counts[job_id, event["kind"]] += 1
        if event["kind"] == "start":
            devices = {(gpu["node_id"], gpu["index"]) for gpu in event["gpus"]}
            assert len(devices) == len(event["gpus"]) == demand[job_id]
            assert all(0 <= index < capacity[node_id] for node_id, index in devices)
            assert not active.intersection(devices)
            active.update(devices)
            by_job[job_id] = devices
        elif event["kind"] == "release":
            active.difference_update(by_job.pop(job_id))
        elif event["kind"] == "blocked":
            assert event["free_gpus"] == sum(capacity.values()) - len(active)

    assert not active and not by_job
    assert result["metrics"]["allocated_gpu_ticks"] == 156
    for job in result["jobs"]:
        if job["status"] == "completed":
            assert counts[job["id"], "start"] == counts[job["id"], "release"] == 1
            assert job["wait"] >= 0
        else:
            assert job["reason"] == "cannot_fit_empty_cluster"
            assert counts[job["id"], "start"] == counts[job["id"], "release"] == 0


def test_reversing_run_order_does_not_carry_state(oracle):
    fifo_then_priority = [run_replay(oracle, policy) for policy in ("fifo", "priority")]
    priority_then_fifo = [run_replay(oracle, policy) for policy in ("priority", "fifo")]
    assert fifo_then_priority == priority_then_fifo[::-1]


@pytest.mark.parametrize("field,value", [("id", True), ("arrival", -1), ("duration", 0), ("gpus", "2"), ("priority", "unknown")])
def test_job_inputs_reject_invalid_values(oracle, field, value):
    job = oracle.jobs[0].model_dump()
    with pytest.raises(ValidationError):
        ReplayJob.model_validate({**job, field: value})


def test_duplicate_job_ids_are_rejected(oracle):
    payload = oracle.model_dump()
    payload["jobs"] = oracle.jobs * 2
    with pytest.raises(ValidationError, match="job IDs must be unique"):
        Scenario.model_validate(payload)


def test_cli_without_database_settings(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("DATABASE_")}
    output = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-m", "app.experiments", str(EXAMPLES / "oracle.json"), "--output", str(output)],
        cwd=ROOT / "backend",
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    report = json.loads(output.read_text())
    assert [run["policy"] for run in report["runs"]] == ["fifo", "priority"]
    assert len(report["trace_sha256"]) == len(report["config_sha256"]) == 64
    assert "27/28" in result.stderr
