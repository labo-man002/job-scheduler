"""Run a paired synthetic queue replay and write a reproducible JSON report."""

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .replay import run_replay
from .replay_input import Scenario


def git_provenance() -> dict:
    source = Path(__file__).resolve()
    repo = source.parents[3]
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(key, None)

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "--no-optional-locks", *args], cwd=repo, env=env, text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        ).strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != repo:
            return {"git_sha": None, "worktree_dirty": None}
        sha = git("rev-parse", "HEAD")
        git("cat-file", "-e", f"{sha}:{source.relative_to(repo).as_posix()}")
        changes = git("status", "--porcelain", "--untracked-files=normal")
    except (OSError, subprocess.SubprocessError):
        return {"git_sha": None, "worktree_dirty": None}
    return {"git_sha": sha, "worktree_dirty": bool(changes)}


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_report(path: Path, serialized: str) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".queue-replay-", delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


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
        output = args.output.resolve() if args.output else None
        if output is not None and output.exists():
            if output.samefile(args.scenario):
                parser.error("report output must differ from the scenario path")
            if not stat.S_ISREG(output.stat().st_mode):
                parser.error("report output must be a regular file")
        scenario_bytes = args.scenario.read_bytes()
        scenario = Scenario.model_validate_json(scenario_bytes)
    except (OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))

    config = {
        "seconds_per_tick": scenario.seconds_per_tick,
        "nodes": [node.model_dump() for node in scenario.nodes],
        "placement": "pack",
        "topology": "linear",
        "service_time": "fixed",
    }
    if scenario.schema_version == 2:
        config["topology"] = scenario.effective_topology.model_dump(mode="json")
        config["queue_policies"] = ["fifo", "priority"]
    trace = [job.model_dump(mode="json") for job in scenario.jobs]
    runs = [run_replay(scenario, policy) for policy in ("fifo", "priority")]
    report = {
        "report_schema_version": scenario.schema_version,
        "scenario_schema_version": scenario.schema_version,
        "source": scenario.source,
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "trace_sha256": canonical_hash(trace),
        "config_sha256": canonical_hash(config),
        "config": config,
        **git_provenance(),
        "runs": runs,
    }
    try:
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if output is not None:
            write_report(output, serialized)
        else:
            sys.stdout.write(serialized)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print_summary(runs)


if __name__ == "__main__":
    main()
