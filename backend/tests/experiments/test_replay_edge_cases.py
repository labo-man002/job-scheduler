import pytest
from pydantic import ValidationError

from app.experiments.replay import run_replay
from app.experiments.replay_input import MAX_NODE_GPUS, MAX_TIME_VALUE, ReplayJob, Scenario


@pytest.fixture
def payload():
    return {
        "schema_version": 1,
        "source": "synthetic",
        "seconds_per_tick": 1,
        "nodes": [{"id": 1, "gpus": 2}],
        "jobs": [{"id": 1, "arrival": 0, "duration": 1, "gpus": 2, "priority": "NORMAL"}],
    }


def test_inventory_limit_is_validated_before_replay(payload):
    payload["nodes"][0]["gpus"] = MAX_NODE_GPUS
    assert Scenario.model_validate(payload).nodes[0].gpus == MAX_NODE_GPUS
    payload["nodes"][0]["gpus"] += 1
    with pytest.raises(ValidationError, match=r"nodes\.0\.gpus"):
        Scenario.model_validate(payload)


@pytest.mark.parametrize("field", ["arrival", "duration"])
def test_clock_input_bounds(payload, field):
    job = payload["jobs"][0]
    job[field] = MAX_TIME_VALUE
    assert getattr(ReplayJob.model_validate(job), field) == MAX_TIME_VALUE
    job[field] += 1
    with pytest.raises(ValidationError, match=field):
        ReplayJob.model_validate(job)


def test_clock_units_limit_and_sparse_clock(payload):
    payload["seconds_per_tick"] = MAX_TIME_VALUE
    payload["jobs"][0]["arrival"] = MAX_TIME_VALUE
    payload["jobs"][0]["duration"] = MAX_TIME_VALUE
    result = run_replay(Scenario.model_validate(payload), "fifo")

    assert [event["tick"] for event in result["events"]] == [MAX_TIME_VALUE, MAX_TIME_VALUE, 2 * MAX_TIME_VALUE]
    assert result["jobs"][0]["finish"] == 2 * MAX_TIME_VALUE
    assert result["metrics"]["occupancy"] == 0.5
    assert result["metrics"]["completed_jobs_per_hour"] > 0

    payload["seconds_per_tick"] += 1
    with pytest.raises(ValidationError, match="seconds_per_tick"):
        Scenario.model_validate(payload)


def test_policy_order_survives_repeated_blocking_and_same_tick_arrivals(payload):
    payload["jobs"][0]["duration"] = 6
    payload["jobs"] += [
        {"id": 50, "arrival": 1, "duration": 1, "gpus": 2, "priority": "NORMAL"},
        {"id": 20, "arrival": 1, "duration": 1, "gpus": 2, "priority": "NORMAL"},
        {"id": 10, "arrival": 2, "duration": 1, "gpus": 2, "priority": "HIGH"},
        {"id": 5, "arrival": 4, "duration": 1, "gpus": 2, "priority": "NORMAL"},
    ]
    scenario = Scenario.model_validate(payload)

    for policy, order in (("fifo", [1, 50, 20, 10, 5]), ("priority", [1, 10, 50, 20, 5])):
        result = run_replay(scenario, policy)
        assert [event["job_id"] for event in result["events"] if event["kind"] == "start"] == order


def test_bad_policy_reports_actionable_error(payload):
    with pytest.raises(ValueError, match="Unknown queue policy: 'typo'"):
        run_replay(Scenario.model_validate(payload), "typo")
