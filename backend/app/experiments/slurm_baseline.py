"""Validate a fixed-duration replay against a Slurm accounting window."""

import argparse
import csv
import hashlib
import io
import json
import re
import stat
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise
from math import ceil
from pathlib import Path
from statistics import mean, median
from typing import Literal

from pydantic import StrictInt

from app.enums import Priority

from .__main__ import git_provenance, write_report
from .replay import POLICIES, ReplayBoundary, run_replay
from .replay_input import ReplayInput, ReplayNode, Scenario

FIELDS = {
    "JobID", "JobIDRaw", "Cluster", "Partition", "Submit", "Eligible", "Start", "End",
    "ElapsedRaw", "State", "Restarts", "Suspended", "ReqTRES", "AllocTRES", "Priority",
}
ALLOCATION_ID = re.compile(r"[0-9]+(?:_[0-9]+)?")
CLASSES = (Priority.LOW, Priority.NORMAL, Priority.HIGH, Priority.URGENT)
UNKNOWN_TIMES = {"", "unknown", "none", "n/a", "invalid"}


def timestamp(value: str) -> int:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if "T" not in value or instant.microsecond:
        raise ValueError(f"Expected an ISO date-time at whole-second resolution: {value!r}")
    # sacct prints timezone-naive labels by default. The export contract requires UTC.
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return int(instant.timestamp())


class Inventory(ReplayInput):
    schema_version: Literal[1]
    data_kind: Literal["synthetic", "measured"]
    trace_source: str
    inventory_source: str
    cluster: str
    partition: str
    snapshot_at: str
    accounting_captured_at: str
    window_start: str
    window_end: str
    gpu_type: str | None = None
    nodes: tuple[ReplayNode, ...]
    priority_class_minimums: dict[Priority, StrictInt]

    def filter_and_validate(self) -> tuple[int, int]:
        left, right = timestamp(self.window_start), timestamp(self.window_end)
        if not timestamp(self.snapshot_at) <= left < right <= timestamp(self.accounting_captured_at):
            raise ValueError("Expected snapshot_at <= window_start < window_end <= accounting_captured_at")
        if not all(value.strip() for value in (self.trace_source, self.inventory_source, self.cluster, self.partition)):
            raise ValueError("Trace source, inventory source, cluster, and partition must be nonempty")
        if not 1 <= len(self.nodes) <= 4 or len({node.id for node in self.nodes}) != len(self.nodes):
            raise ValueError("Inventory must contain one to four nodes with unique IDs")
        if set(self.priority_class_minimums) != set(CLASSES):
            raise ValueError("Priority mapping requires LOW, NORMAL, HIGH, and URGENT minimums")
        thresholds = [self.priority_class_minimums[rank] for rank in CLASSES]
        if thresholds[0] != 0 or any(lower >= upper for lower, upper in pairwise(thresholds)):
            raise ValueError("Priority minimums must start at 0 and strictly increase")
        return left, right

    def priority_class(self, priority: int) -> Priority:
        return next(rank for rank in reversed(CLASSES) if priority >= self.priority_class_minimums[rank])


class Excluded(ValueError):
    def __init__(self, reason: str, *, right_censored: bool = False):
        super().__init__(reason)
        self.right_censored = right_censored


@dataclass(frozen=True)
class ObservedJob:
    job_id: str
    raw_id: str
    submit: int
    eligible: int
    start: int
    end: int
    requested: int
    allocated: int
    priority: int

    @property
    def duration(self) -> int:
        return self.end - self.start


def parse_accounting(trace: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(trace.decode("utf-8-sig")), delimiter="|", quoting=csv.QUOTE_NONE)
    header = reader.fieldnames or []
    if FIELDS - set(header):
        raise ValueError(f"Missing sacct columns: {', '.join(sorted(FIELDS - set(header)))}")
    if len(header) != len(set(header)):
        raise ValueError("Duplicate sacct columns")
    rows = []
    for line, row in enumerate(reader, start=2):
        if None in row or None in row.values():
            raise ValueError(f"Malformed sacct row at line {line}: incorrect number of columns")
        rows.append({name: value.strip() for name, value in row.items()})
    return rows


def gpu_count(tres: str, gpu_type: str | None) -> int:
    resources: dict[str, int] = {}
    for entry in filter(None, tres.split(",")):
        key, separator, value = entry.partition("=")
        if key == "gres/gpu" or key.startswith("gres/gpu:"):
            if not separator or not value.isascii() or not value.isdecimal() or key in resources:
                raise Excluded("invalid_gpu_tres")
            resources[key] = int(value)
        elif key.startswith(("gres/mps", "gres/shard", "gres/mig")):
            raise Excluded("unsupported_gpu_sharing")
        elif not separator and key.startswith("gres/"):
            raise Excluded("invalid_gpu_tres")
    typed = {key.removeprefix("gres/gpu:"): value for key, value in resources.items() if key != "gres/gpu"}
    if typed and (len(typed) != 1 or gpu_type not in typed):
        raise Excluded("unsupported_gpu_type")
    total = resources.get("gres/gpu")
    typed_total = sum(typed.values())
    if total is not None and typed and total != typed_total:
        raise Excluded("inconsistent_gpu_tres")
    return typed_total if total is None else total


def read_time(row: dict[str, str], field: str, *, optional: bool = False) -> int | None:
    value = row[field]
    if value.lower() in UNKNOWN_TIMES:
        if optional:
            return None
        raise Excluded(f"missing_{field.lower()}")
    try:
        return timestamp(value)
    except (OverflowError, ValueError) as exc:
        raise Excluded(f"invalid_{field.lower()}") from exc


def integer_field(row: dict[str, str], field: str) -> int:
    value = row[field]
    if value.lower() in UNKNOWN_TIMES:
        raise Excluded(f"missing_{field.lower()}")
    if not value.isascii() or not value.isdecimal():
        raise Excluded(f"invalid_{field.lower()}")
    return int(value)


def import_job(row: dict[str, str], inventory: Inventory, left: int, right: int, capture: int, capacity: int) -> ObservedJob:
    submit = read_time(row, "Submit")
    eligible = read_time(row, "Eligible")
    start = read_time(row, "Start", optional=True)
    end = read_time(row, "End", optional=True)
    state = row["State"]
    if eligible >= right or (end is not None and end <= left):
        raise Excluded("outside_observation_window")
    if submit > eligible or (start is not None and start < eligible):
        raise Excluded("invalid_timestamp_order")
    if integer_field(row, "Restarts"):
        raise Excluded("unsupported_requeued_job")
    if row["Suspended"] not in {"0", "00:00:00", "0:00:00", "0-00:00:00"}:
        raise Excluded("unsupported_or_missing_suspension_history")
    if row.get("Reservation", "") not in {"", "None", "N/A"}:
        raise Excluded("unsupported_reservation")
    if not row["ReqTRES"]:
        raise Excluded("missing_reqtres")
    requested = gpu_count(row["ReqTRES"], inventory.gpu_type)
    if requested == 0:
        if gpu_count(row["AllocTRES"], inventory.gpu_type):
            raise Excluded("requested_and_allocated_gpu_counts_differ")
        raise Excluded("no_requested_gpu")
    if state in {"RUNNING", "COMPLETING", "PENDING"}:
        raise Excluded("right_censored_service_unknown", right_censored=True)
    if not state:
        raise Excluded("missing_state")
    if state != "COMPLETED":
        raise Excluded("unsupported_terminal_state")
    if start is None or end is None:
        raise Excluded("missing_start_or_end")
    elapsed = integer_field(row, "ElapsedRaw")
    if elapsed <= 0 or end - start != elapsed:
        raise Excluded("invalid_or_inconsistent_service_duration")
    if end > capture:
        raise Excluded("completion_after_capture")
    allocated = gpu_count(row["AllocTRES"], inventory.gpu_type)
    if not allocated:
        raise Excluded("missing_allocated_gpu")
    if requested != allocated:
        raise Excluded("requested_and_allocated_gpu_counts_differ")
    if requested > capacity:
        raise Excluded("whole_gpu_count_exceeds_inventory")
    priority = integer_field(row, "Priority")
    return ObservedJob(row["JobID"], row["JobIDRaw"], submit, eligible, start, end, requested, allocated, priority)


def distribution(values: list[int]) -> dict:
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "min": None, "max": None}
    ordered = sorted(values)
    return {
        "count": len(values), "mean": mean(values), "p50": median(values),
        "p95": ordered[ceil(0.95 * len(ordered)) - 1], "min": ordered[0], "max": ordered[-1],
    }


def compare_occupancy(
    intervals: list[tuple[int, int, int, int]], left: int, right: int, capacity: int,
) -> dict:
    changes: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    changes[left]
    changes[right]
    for start, end, amount, series in intervals:
        start, end = max(start, left), min(end, right)
        if start < end:
            changes[start][series] += amount
            changes[end][series] -= amount
    observed = simulated = observed_total = simulated_total = absolute_total = 0
    previous = left
    segments = []
    for tick, (observed_change, simulated_change) in sorted(changes.items()):
        length = tick - previous
        if length:
            observed_total += length * observed
            simulated_total += length * simulated
            absolute_total += length * abs(simulated - observed)
            segments.append({"from_second": previous - left, "to_second": tick - left,
                             "observed_gpus": observed, "simulated_gpus": simulated})
        observed += observed_change
        simulated += simulated_change
        previous = tick
    available = (right - left) * capacity
    return {
        "available_gpu_seconds": available,
        "observed_gpu_seconds": observed_total,
        "simulated_gpu_seconds": simulated_total,
        "observed_occupancy": observed_total / available,
        "simulated_occupancy": simulated_total / available,
        "signed_gpu_seconds_error": simulated_total - observed_total,
        "absolute_pointwise_gpu_seconds_error": absolute_total,
        "occupancy_mae": absolute_total / available,
        "observed_exceeds_inventory": any(segment["observed_gpus"] > capacity for segment in segments),
        "segments": segments,
    }


def compare_jobs(jobs: list[ObservedJob], replay: dict, origin: int, left: int, right: int) -> tuple[list[dict], dict]:
    comparisons = []
    for outcome, job in zip(replay["jobs"], jobs, strict=True):
        simulated = None if outcome["status"] != "completed" else origin + outcome["start"]
        observed_in_window = left <= job.start < right
        simulated_in_window = simulated is not None and left <= simulated < right
        both = observed_in_window and simulated_in_window
        comparisons.append({
            "replay_job_id": outcome["id"], "job_id": job.job_id, "job_id_raw": job.raw_id,
            "priority": job.priority, "replay_class": outcome["priority"],
            "submit_second": job.submit - left, "eligible_second": job.eligible - left,
            "requested_gpus": job.requested, "allocated_gpus": job.allocated, "service_seconds": job.duration,
            "observed_start_second": job.start - left, "observed_end_second": job.end - left,
            "simulated_start_second": None if simulated is None else simulated - left,
            "simulated_end_second": None if simulated is None else simulated + job.duration - left,
            "carry_in_running": job.start < left,
            "carry_in_waiting": job.eligible < left <= job.start,
            "observed_start_right_censored": job.start >= right,
            "observed_completion_right_censored": job.end > right,
            "observed_wait_seconds": job.start - job.eligible if observed_in_window else None,
            "simulated_wait_seconds": simulated - job.eligible if simulated_in_window else None,
            "start_error_seconds": simulated - job.start if both else None,
        })
    errors = [row["start_error_seconds"] for row in comparisons if row["start_error_seconds"] is not None]
    classes = {}
    for priority in CLASSES:
        group = [row for row in comparisons if row["replay_class"] == priority.value]
        classes[priority.value] = {
            "observed_eligible_wait_seconds": distribution([
                row["observed_wait_seconds"] for row in group if row["observed_wait_seconds"] is not None
            ]),
            "simulated_eligible_wait_seconds": distribution([
                row["simulated_wait_seconds"] for row in group if row["simulated_wait_seconds"] is not None
            ]),
            "paired_wait_error_seconds": distribution([
                row["start_error_seconds"] for row in group if row["start_error_seconds"] is not None
            ]),
        }
    outliers = sorted(
        (row for row in comparisons if row["start_error_seconds"] is not None),
        key=lambda row: (-abs(row["start_error_seconds"]), row["job_id"], row["job_id_raw"]),
    )[:10]
    return comparisons, {
        "observed_start_count": sum(row["observed_wait_seconds"] is not None for row in comparisons),
        "simulated_start_count": sum(row["simulated_wait_seconds"] is not None for row in comparisons),
        "paired_start_error_seconds": distribution(errors),
        "paired_absolute_start_error_seconds": distribution([abs(error) for error in errors]),
        "largest_paired_start_discrepancies": outliers,
        "unpaired_starts": [
            {"job_id": row["job_id"], "job_id_raw": row["job_id_raw"],
             "observed_start_second": row["observed_start_second"], "simulated_start_second": row["simulated_start_second"]}
            for row in comparisons
            if (row["observed_wait_seconds"] is None) != (row["simulated_wait_seconds"] is None)
        ],
        "waits_by_replay_class": classes,
    }


def build_report(trace: bytes, inventory_bytes: bytes, policy: str) -> dict:
    if policy not in POLICIES:
        raise ValueError(f"Unknown queue policy: {policy!r}")
    inventory = Inventory.model_validate_json(inventory_bytes)
    left, right = inventory.filter_and_validate()
    capture = timestamp(inventory.accounting_captured_at)
    rows = parse_accounting(trace)
    capacity = sum(node.gpus for node in inventory.nodes)
    jobs = []
    exclusions = []
    scoped = [row for row in rows if (row["Cluster"], row["Partition"]) == (inventory.cluster, inventory.partition)]
    allocations = [row for row in scoped if ALLOCATION_ID.fullmatch(row["JobID"])]
    ids = Counter(row["JobID"] for row in allocations)
    raw_ids = Counter(row["JobIDRaw"] for row in allocations)
    for row in rows:
        try:
            if "." in row["JobID"] or "." in row["JobIDRaw"]:
                raise Excluded("job_step")
            if (row["Cluster"], row["Partition"]) != (inventory.cluster, inventory.partition):
                raise Excluded("outside_inventory_cluster_or_partition")
            if not ALLOCATION_ID.fullmatch(row["JobID"]) or not ALLOCATION_ID.fullmatch(row["JobIDRaw"]):
                raise Excluded("unsupported_or_missing_allocation_id")
            if ids[row["JobID"]] > 1 or raw_ids[row["JobIDRaw"]] > 1:
                raise Excluded("duplicate_allocation_identity")
            jobs.append(import_job(row, inventory, left, right, capture, capacity))
        except Excluded as excluded:
            exclusions.append({
                "job_id": row["JobID"], "job_id_raw": row["JobIDRaw"],
                "state": row["State"], "reason": str(excluded), "right_censored": excluded.right_censored,
            })
    exclusions_by_reason = dict(sorted(Counter(exclusion["reason"] for exclusion in exclusions).items()))
    benign_exclusions = {"job_step", "outside_inventory_cluster_or_partition", "outside_observation_window", "no_requested_gpu"}
    report = {
        "report_schema_version": 1, "policy": policy, "inputs": inventory.model_dump(mode="json"),
        "accounting_sha256": hashlib.sha256(trace).hexdigest(),
        "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "seconds_per_tick": 1,
        "input_rows": len(rows), "included_jobs": len(jobs),
        "exclusions_by_reason": exclusions_by_reason, "exclusions": exclusions,
        "right_censored_excluded_jobs": sum(exclusion["right_censored"] for exclusion in exclusions),
        "scope": "selected_cohort_on_fixed_inventory" if jobs else "no_supported_jobs",
        "potentially_incomplete_slice": bool(exclusions_by_reason.keys() - benign_exclusions),
        "unsupported_behaviors": [
            "backfill and time limits", "changing Slurm priority, fair-share and QoS", "CPU, memory and license constraints",
            "preemption, reservations and job dependencies", "GPU sharing, heterogeneous GPUs and resource changes",
            "exact historical placements, topology and per-job interference",
        ],
        **git_provenance(),
    }
    if not jobs:
        return {**report, "jobs": [], "start_and_wait": None, "occupancy": None}
    # Resolve ties without using accounting row order or observed starts.
    jobs.sort(key=lambda job: (job.eligible, tuple(int(part) for part in job.raw_id.split("_")), job.job_id))
    boundary_jobs = [job for job in jobs if job.start < left]
    if sum(job.allocated for job in boundary_jobs) > capacity:
        return {
            **report, "scope": "inconsistent_boundary_capacity", "potentially_incomplete_slice": True,
            "validation_error": "Observed carry-in allocations exceed inventory capacity",
            "boundary_running_job_ids": [job.job_id for job in boundary_jobs],
            "jobs": [], "start_and_wait": None, "occupancy": None,
        }
    origin = min(left, jobs[0].eligible)
    scenario = Scenario.model_validate({
        "schema_version": 1, "source": inventory.trace_source, "seconds_per_tick": 1,
        "nodes": inventory.nodes,
        "jobs": [
            {"id": i, "arrival": job.eligible - origin, "duration": job.duration,
             "gpus": job.requested, "priority": inventory.priority_class(job.priority)}
            for i, job in enumerate(jobs, start=1)
        ],
    })
    boundary = ReplayBoundary(
        left - origin, {i: job.start - origin for i, job in enumerate(jobs, start=1) if job.start < left},
    )
    replay = run_replay(scenario, policy, boundary=boundary)
    observations, start_and_wait = compare_jobs(jobs, replay, origin, left, right)
    intervals = [(job.start, job.end, job.allocated, 0) for job in jobs]
    for row in observations:
        if row["simulated_start_second"] is not None:
            intervals.append((
                left + row["simulated_start_second"], left + row["simulated_end_second"], row["requested_gpus"], 1,
            ))
    occupancy = compare_occupancy(intervals, left, right, capacity)
    return {
        **report,
        "potentially_incomplete_slice": report["potentially_incomplete_slice"] or occupancy["observed_exceeds_inventory"],
        "jobs": observations,
        "boundary": {
            "running_count": sum(row["carry_in_running"] for row in observations),
            "waiting_count": sum(row["carry_in_waiting"] for row in observations),
            "start_right_censored_count": sum(row["observed_start_right_censored"] for row in observations),
            "completion_right_censored_count": sum(row["observed_completion_right_censored"] for row in observations),
        },
        "start_and_wait": start_and_wait, "occupancy": occupancy,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Slurm sacct --parsable2 file with its header")
    parser.add_argument("inventory", type=Path, help="Versioned JSON inventory and observation window")
    parser.add_argument("--policy", choices=POLICIES, default="fifo", help="Baseline replay policy (default: fifo)")
    parser.add_argument("--output", type=Path, help="Write report JSON to a file (default: stdout)")
    args = parser.parse_args()
    try:
        output = args.output.resolve() if args.output else None
        if output is not None and output.exists():
            if not stat.S_ISREG(output.stat().st_mode):
                raise ValueError("report output must be a regular file")
            if any(output.samefile(path) for path in (args.trace, args.inventory)):
                raise ValueError("report output must differ from the trace and inventory paths")
        report = build_report(args.trace.read_bytes(), args.inventory.read_bytes(), args.policy)
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if output is None:
            sys.stdout.write(serialized)
        else:
            write_report(output, serialized)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
