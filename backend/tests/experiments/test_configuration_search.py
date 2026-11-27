import json
import subprocess
import sys
from pathlib import Path

from app.experiments.configuration_search import SearchSpec, search_configurations
from app.experiments.replay_input import Scenario

ROOT = Path(__file__).resolve().parents[3]
ORACLE = ROOT / "examples" / "queue-replay" / "oracle.json"
SPEC = ROOT / "examples" / "configuration-search" / "spec.json"


def test_capacity_search_finds_hand_checkable_optimum_and_ties():
    scenario = Scenario.model_validate_json(ORACLE.read_bytes())
    spec = SearchSpec.model_validate_json(SPEC.read_bytes())
    report = search_configurations(scenario, spec)
    assert report["feasible_rankings"] == [
        {"rank": 1, "name": "four-gpu", "objective_value": 9},
        {"rank": 2, "name": "baseline", "objective_value": 14},
        {"rank": 2, "name": "priority", "objective_value": 14},
    ]
    assert report["best_candidates"] == ["four-gpu"]
    by_name = {alternative["name"]: alternative for alternative in report["alternatives"]}
    assert by_name["four-gpu"]["metric_delta_from_baseline"]["makespan_ticks_from_zero"] == -5
    assert by_name["one-gpu"]["violations"] == ["unscheduled_exceeds_limit"]
    assert by_name["disconnected-two-gpu"]["unscheduled_jobs"] == [
        {"id": 1, "reason": "no_connected_allocation"},
        {"id": 2, "reason": "no_connected_allocation"},
    ]


def test_no_candidate_can_meet_completion_and_capacity_limits():
    scenario = Scenario.model_validate_json(ORACLE.read_bytes())
    spec = SearchSpec.model_validate(
        {
            **json.loads(SPEC.read_bytes()),
            "constraints": {"max_gpu_capacity": 1, "max_unscheduled_jobs": 0},
        }
    )
    report = search_configurations(scenario, spec)
    assert report["status"] == "no_feasible_candidate"
    assert report["feasible_rankings"] == report["best_candidates"] == []
    assert not report["baseline"]["feasible"]


def test_identical_control_and_maximization():
    scenario = Scenario.model_validate_json(ORACLE.read_bytes())
    spec = SearchSpec.model_validate(
        {
            "schema_version": 1,
            "baseline_policy": "fifo",
            "objective": "completed_jobs_per_hour",
            "constraints": {},
            "alternatives": [
                {"name": "control", "policy": "fifo"},
                {"name": "four-gpu", "policy": "fifo", "nodes": [{"id": 1, "gpus": 4}]},
            ],
        }
    )
    report = search_configurations(scenario, spec)
    assert report["objective"]["direction"] == "maximize"
    assert report["best_candidates"] == ["four-gpu"]
    baseline, control = report["baseline"], report["alternatives"][0]
    assert baseline["config_sha256"] == control["config_sha256"]
    assert control["metric_delta_from_baseline"]["completed_jobs_per_hour"] == 0
    assert control["metric_delta_from_baseline"]["cross_leaf_placements"] is None


def test_cli_deterministically_reports_shared_trace_and_input_hashes():
    command = [sys.executable, "-m", "app.experiments.configuration_search", str(ORACLE), str(SPEC)]
    results = [
        subprocess.run(command, cwd=ROOT / "backend", check=True, text=True, capture_output=True).stdout
        for _ in range(2)
    ]
    assert results[0] == results[1]
    report = json.loads(results[0])
    assert report["best_candidates"] == ["four-gpu"]
    assert report["trace_jobs"] == 3
    for key in ("scenario_sha256", "search_sha256", "trace_sha256"):
        assert len(report[key]) == 64
