import json
from pathlib import Path

import pytest

from app.experiments.slurm_baseline import build_report, compare_occupancy

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "slurm-baseline"
TRACE = (EXAMPLE / "accounting.psv").read_bytes()
INVENTORY = (EXAMPLE / "inventory.json").read_bytes()


def test_synthetic_baseline_reconstructs_boundary_and_reports_errors():
    report = build_report(TRACE, INVENTORY, "fifo")
    assert report["inputs"]["data_kind"] == "synthetic"
    assert report["input_rows"] == 15
    assert report["included_jobs"] == 6
    assert report["boundary"] == {
        "running_count": 1,
        "waiting_count": 1,
        "start_right_censored_count": 1,
        "completion_right_censored_count": 2,
    }
    jobs = {job["job_id"]: job for job in report["jobs"]}
    assert jobs["100"]["simulated_start_second"] == -5
    assert jobs["100"]["start_error_seconds"] is None
    assert jobs["101_2"]["job_id_raw"] == "107"
    assert jobs["101_2"]["submit_second"] == -8
    assert jobs["101_2"]["observed_wait_seconds"] == 7
    assert jobs["105"]["observed_wait_seconds"] is None
    assert report["occupancy"]["observed_gpu_seconds"] == 52
    assert report["occupancy"]["simulated_gpu_seconds"] == 56
    assert report["occupancy"]["available_gpu_seconds"] == 60
    assert report["occupancy"]["occupancy_mae"] == pytest.approx(4 / 60)
    assert report["start_and_wait"]["paired_start_error_seconds"]["count"] == 4
    assert report["start_and_wait"]["paired_absolute_start_error_seconds"]["mean"] == 1
    assert report["exclusions_by_reason"]["job_step"] == 1
    assert report["exclusions_by_reason"]["missing_eligible"] == 1
    assert report["exclusions_by_reason"]["requested_and_allocated_gpu_counts_differ"] == 1
    assert report["right_censored_excluded_jobs"] == 1
    assert report["potentially_incomplete_slice"]


def test_equal_eligibility_order_and_replay_ignore_observed_start():
    # Alter the accounting outcome while retaining recorded duration and eligibility.
    changed = TRACE.replace(b"T12:00:17|2026-11-26T12:00:27", b"T12:00:18|2026-11-26T12:00:28")
    old = build_report(TRACE, INVENTORY, "fifo")
    new = build_report(changed, INVENTORY, "fifo")
    assert [job["simulated_start_second"] for job in old["jobs"]] == [job["simulated_start_second"] for job in new["jobs"]]
    assert old["start_and_wait"]["paired_start_error_seconds"] != new["start_and_wait"]["paired_start_error_seconds"]

    tied = TRACE.replace(b"T12:00:03|2026-11-26T12:00:03|2026-11-26T12:00:17", b"T12:00:02|2026-11-26T12:00:02|2026-11-26T12:00:17")
    header, *records = tied.splitlines()
    order = build_report(tied, INVENTORY, "fifo")
    reverse = build_report(b"\n".join([header, *reversed(records)]), INVENTORY, "fifo")
    assert order["jobs"] == reverse["jobs"]


def test_bad_inventory_does_not_generate_an_accuracy_claim():
    data = json.loads(INVENTORY)
    data["nodes"] = [{"id": 1, "gpus": 3}]
    header, *rows = TRACE.splitlines()
    additional = rows[0].replace(b"100|100|", b"900|900|")
    trace = b"\n".join([header, *rows, additional])
    report = build_report(trace, json.dumps(data).encode(), "fifo")
    assert report["scope"] == "inconsistent_boundary_capacity"
    assert report["occupancy"] is None
    assert report["boundary_running_job_ids"] == ["100", "900"]


def test_single_carry_in_waiting_job_dispatches_at_left_boundary():
    header, *rows = TRACE.splitlines()
    report = build_report(b"\n".join([header, rows[2]]), INVENTORY, "fifo")
    assert report["jobs"][0]["carry_in_waiting"]
    assert report["jobs"][0]["simulated_start_second"] == 0


def test_duplicate_allocation_identity_excludes_both_rows():
    header, first, *_ = TRACE.splitlines()
    report = build_report(b"\n".join([header, first, first]), INVENTORY, "fifo")
    assert report["scope"] == "no_supported_jobs"
    assert report["exclusions_by_reason"] == {"duplicate_allocation_identity": 2}
    assert report["start_and_wait"] is None


def test_equal_aggregate_occupancy_can_hide_pointwise_errors():
    result = compare_occupancy([(0, 4, 2, 0), (4, 8, 2, 1)], 0, 8, 2)
    assert result["signed_gpu_seconds_error"] == 0
    assert result["absolute_pointwise_gpu_seconds_error"] == 16
    assert result["occupancy_mae"] == 1


def test_exported_scenario_round_trips_without_observed_boundary(tmp_path, monkeypatch):
    from app.experiments.replay_input import Scenario
    from app.experiments.slurm_baseline import main

    target = tmp_path / "scenario.json"
    baseline = tmp_path / "baseline.json"
    monkeypatch.setattr("sys.argv", ["slurm_baseline", str(EXAMPLE / "accounting.psv"),
                        str(EXAMPLE / "inventory.json"), "--scenario-output", str(target), "--output", str(baseline)])
    main()
    scenario = Scenario.model_validate_json(target.read_bytes())
    report = json.loads(baseline.read_bytes())
    assert "empty-cluster counterfactual" in scenario.source
    assert report["accounting_sha256"] in scenario.source
    assert len(scenario.jobs) == report["included_jobs"]
    assert report["boundary"]["running_count"] == 1
    assert "normalized_scenario" not in report
