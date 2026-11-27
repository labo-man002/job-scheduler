"""Measure paired replay and optionally a disposable instance's persisted history."""

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "queue-replay" / "contention.json"


def encode(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def generated_window(size, nodes):
    fixture = json.loads(FIXTURE.read_bytes())
    original = fixture["jobs"]
    jobs = []
    for index in range(size):
        seed = original[index % len(original)]
        arrivals = index // len(original) * 16 + seed["arrival"]
        jobs.append(dict(seed, id=index + 1, arrival=arrivals))
    return dict(
        fixture,
        source=f"Synthetic repeated contention batches ({size} jobs)",
        nodes=[{"id": index + 1, "gpus": 2} for index in range(nodes)],
        jobs=jobs,
    )


def worker(size, nodes, scenario_path):
    from app.experiments.replay import run_replay
    from app.experiments.replay_input import Scenario

    data = json.loads(scenario_path.read_bytes()) if scenario_path else generated_window(size, nodes)
    scenario = Scenario.model_validate(data)
    effective_input = encode(scenario.model_dump(mode="json"))
    started = time.perf_counter()
    runs = [run_replay(scenario, policy) for policy in ("fifo", "priority")]
    replay_seconds = time.perf_counter() - started
    started = time.perf_counter()
    result_bytes = len(encode(runs))
    encode_seconds = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "source": scenario.source,
        "jobs": len(scenario.jobs),
        "nodes": len(scenario.nodes),
        "gpus": sum(node.gpus for node in scenario.nodes),
        "paired_replay_seconds": replay_seconds,
        "paired_jobs_per_second": len(scenario.jobs) / replay_seconds,
        "result_encode_seconds": encode_seconds,
        "peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "events": sum(len(run["events"]) for run in runs),
        "completed_per_policy": [run["metrics"]["completed"] for run in runs],
        "input_json_bytes": len(effective_input),
        "input_sha256": hashlib.sha256(effective_input).hexdigest(),
        "paired_output_json_bytes": result_bytes,
    }


def http_json(url, data=None):
    request = Request(url, data=encode(data) if data is not None else None, headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    elapsed = time.perf_counter() - started
    return json.loads(payload), elapsed, len(payload)


def history_benchmark(url, size, nodes, trace, seed_runs, reads):
    listing = f"{url.rstrip('/')}/replay/runs"
    snapshot = json.loads(trace.read_bytes()) if trace else generated_window(size, nodes)
    created = []
    saves = []
    for _ in range(seed_runs):
        detail, elapsed, byte_count = http_json(listing, {"request_id": str(uuid4()), "scenario": snapshot})
        created.append(detail["id"])
        saves.append({"seconds": elapsed, "bytes": byte_count})
    history = []
    details = []
    for index in range(reads):
        page, elapsed, byte_count = http_json(f"{listing}?limit=20&offset=0")
        history.append({"seconds": elapsed, "bytes": byte_count, "returned_runs": len(page["items"])})
        detail, elapsed, byte_count = http_json(f"{listing}/{created[index % len(created)]}")
        details.append({"seconds": elapsed, "bytes": byte_count, "id": detail["id"]})
    return {
        "seeded_runs": seed_runs,
        **{
            name: {"median_seconds": statistics.median(row["seconds"] for row in results), "samples": results}
            for name, results in (("save", saves), ("history", history), ("detail", details))
        },
    }


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def cpu_model():
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=positive_int, default=[100, 1000, 5000])
    parser.add_argument("--nodes", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--repetitions", type=positive_int, default=3)
    parser.add_argument("--scenario", type=Path, help="Use this versioned replay JSON instead of generated windows")
    parser.add_argument("--api-url", help="Local replay API. Seeding adds runs in this disposable instance")
    parser.add_argument("--seed-runs", type=positive_int, default=25)
    parser.add_argument("--history-reads", type=positive_int, default=10)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.sizes[0], args.nodes, args.scenario)))
        return

    rows = []
    for size in args.sizes if args.scenario is None else [1]:
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--nodes", str(args.nodes), "--sizes", str(size)]
        if args.scenario is not None:
            command.extend(["--scenario", str(args.scenario.resolve())])
        samples = [
            json.loads(subprocess.check_output(command, timeout=180))
            for _ in range(args.repetitions)
        ]
        rows.append({
            "samples": samples,
            "median_replay_seconds": statistics.median(sample["paired_replay_seconds"] for sample in samples),
            "max_peak_rss_bytes": max(sample["peak_rss_bytes"] for sample in samples),
        })
    from app.experiments.__main__ import git_provenance

    report = {
        **git_provenance(),
        "environment": {
            "python": platform.python_version(),
            "system": platform.platform(),
            "cpu": cpu_model(),
            "logical_cpu_count": os.cpu_count(),
        },
        "windows": rows,
        "persistence": None,
    }
    if args.api_url is not None:
        report["persistence"] = history_benchmark(
            args.api_url, args.sizes[-1], args.nodes, args.scenario, args.seed_runs, args.history_reads
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
