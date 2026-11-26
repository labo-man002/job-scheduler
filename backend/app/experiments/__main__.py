"""Run a paired synthetic queue replay and write a reproducible JSON report."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from .replay_input import Scenario


def git_provenance() -> dict:
    repo = Path(__file__).resolve().parents[3]
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.DEVNULL
        ).strip()
        changes = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo, text=True, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return {"git_sha": None, "worktree_dirty": None}
    return {"git_sha": sha, "worktree_dirty": bool(changes)}


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def print_summary(runs: list[dict]) -> None:
    print("Policy     Done  Unscheduled  End tick    GPU-ticks   Mean wait per class (count)", file=sys.stderr)
    for run in runs:
        metrics = run["metrics"]
        usage = f"{metrics['allocated_gpu_ticks']}/{metrics['available_gpu_ticks']}"
        waits = ", ".join(
            f"{priority} {values['mean']:.2f} ({values['count']})"
            for priority, values in metrics["wait_ticks_by_priority"].items()
        )
        print(
            f"{run['policy']:<10} {metrics['completed']:>4}  {metrics['unscheduled']:>11}  "
            f"{metrics['makespan_ticks_from_zero']:>8}  {usage:>11}   {waits}",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="A versioned JSON experiment scenario")
    parser.add_argument("--output", type=Path, help="Write report JSON to a file (default: stdout)")
    args = parser.parse_args()

    try:
        if args.output and args.output.resolve() == args.scenario.resolve():
            parser.error("report output must differ from the scenario path")
        scenario = Scenario.model_validate_json(args.scenario.read_bytes())
    except (OSError, ValueError) as error:
        parser.error(str(error))

    # ORM model imports construct an engine lazily bound to its first
    # connection. Replay never opens a session or connects to that engine.
    for key, value in {
        "DATABASE_HOSTNAME": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_USERNAME": "replay",
        "DATABASE_PASSWORD": "replay",
        "DATABASE_NAME": "replay",
    }.items():
        os.environ.setdefault(key, value)

    from .replay import run_replay

    config = {
        "seconds_per_tick": scenario.seconds_per_tick,
        "nodes": [node.model_dump() for node in scenario.nodes],
        "placement": "pack",
        "topology": "linear",
        "service_time": "fixed",
    }
    trace = [job.model_dump(mode="json") for job in scenario.jobs]
    runs = [run_replay(scenario, policy) for policy in ("fifo", "priority")]
    report = {
        "report_schema_version": 1,
        "scenario_schema_version": scenario.schema_version,
        "source": scenario.source,
        "trace_sha256": canonical_hash(trace),
        "config_sha256": canonical_hash(config),
        "config": config,
        **git_provenance(),
        "runs": runs,
    }
    serialized = json.dumps(report, indent=2) + "\n"
    try:
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
    except OSError as error:
        parser.error(str(error))
    print_summary(runs)


if __name__ == "__main__":
    main()
