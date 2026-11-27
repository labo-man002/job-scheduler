"""Rank a bounded set of cluster configurations on one fixed-duration replay trace."""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, StrictInt, StringConstraints, model_validator

from .__main__ import canonical_hash, git_provenance
from .replay import run_replay
from .replay_input import PositiveInt, ReplayInput, ReplayNode, ReplayTopology, Scenario

Policy = Literal["fifo", "priority"]
Objective = Literal["makespan_ticks_from_zero", "mean_wait_ticks", "completed_jobs_per_hour", "gpu_capacity"]
MAX_ALTERNATIVES = 32


class Constraints(ReplayInput):
    max_gpu_capacity: PositiveInt | None = None
    max_unscheduled_jobs: Annotated[StrictInt, Field(ge=0)] = 0
    max_mean_wait_ticks: Annotated[FiniteFloat, Field(ge=0, strict=True)] | None = None


class Alternative(ReplayInput):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
    policy: Policy
    nodes: Annotated[tuple[ReplayNode, ...], Field(min_length=1, max_length=4)] | None = None
    topology: ReplayTopology | None = None


class SearchSpec(ReplayInput):
    schema_version: Literal[1]
    baseline_policy: Policy
    objective: Objective
    constraints: Constraints
    alternatives: Annotated[tuple[Alternative, ...], Field(min_length=1, max_length=MAX_ALTERNATIVES)]

    @model_validator(mode="after")
    def validate_names(self) -> "SearchSpec":
        names = {alternative.name for alternative in self.alternatives}
        if "baseline" in names or len(names) != len(self.alternatives):
            raise ValueError("alternative names must be unique and cannot use the name 'baseline'")
        return self


def analyze_candidate(name: str, scenario: Scenario, policy: Policy, spec: SearchSpec) -> dict:
    config = {
        "policy": policy,
        "nodes": [node.model_dump(mode="json") for node in scenario.nodes],
        "topology": scenario.effective_topology.model_dump(mode="json"),
    }
    run = run_replay(scenario, policy)
    metrics = run["metrics"]
    completed_waits = [job["wait"] for job in run["jobs"] if job["status"] == "completed"]
    metrics["mean_wait_ticks"] = mean(completed_waits) if completed_waits else None
    metrics["gpu_capacity"] = sum(node.gpus for node in scenario.nodes)
    if not completed_waits:
        # The replay's zero horizon sentinel must not win a minimum-time search.
        metrics["makespan_ticks_from_zero"] = None
    objective_value = metrics[spec.objective]
    limits = (
        ("gpu_capacity", spec.constraints.max_gpu_capacity),
        ("unscheduled", spec.constraints.max_unscheduled_jobs),
        ("mean_wait_ticks", spec.constraints.max_mean_wait_ticks),
    )
    violations = [
        f"{metric}_unavailable" if metrics[metric] is None else f"{metric}_exceeds_limit"
        for metric, limit in limits
        if limit is not None and (metrics[metric] is None or metrics[metric] > limit)
    ]
    if objective_value is None and f"{spec.objective}_unavailable" not in violations:
        violations.append(f"{spec.objective}_unavailable")
    return {
        "name": name,
        "config": config,
        "config_sha256": canonical_hash(config),
        "objective_value": objective_value,
        "feasible": not violations,
        "violations": violations,
        "metrics": metrics,
        "unscheduled_jobs": [
            {"id": job["id"], "reason": job["reason"]} for job in run["jobs"] if job["status"] == "unscheduled"
        ],
    }


def search_configurations(scenario: Scenario, spec: SearchSpec) -> dict:
    """Replay the baseline and each explicit alternative. Never alter job inputs."""
    baseline = analyze_candidate("baseline", scenario, spec.baseline_policy, spec)
    alternatives = []
    for candidate in spec.alternatives:
        # The baseline owns the trace. Alternatives can override only the configuration.
        topology = candidate.topology or scenario.topology
        candidate_scenario = Scenario(
            schema_version=2 if topology is not None else 1,
            source=scenario.source,
            seconds_per_tick=scenario.seconds_per_tick,
            jobs=scenario.jobs,
            nodes=candidate.nodes or scenario.nodes,
            topology=topology,
        )
        alternative = analyze_candidate(candidate.name, candidate_scenario, candidate.policy, spec)
        alternatives.append(alternative)

    baseline_metrics = baseline["metrics"]
    for alternative in alternatives:
        candidate_metrics = alternative["metrics"]
        deltas = {}
        for metric, baseline_value in baseline_metrics.items():
            if metric == "wait_ticks_by_priority":
                continue
            candidate_value = candidate_metrics.get(metric)
            deltas[metric] = candidate_value - baseline_value if candidate_value is not None and baseline_value is not None else None
        alternative["metric_delta_from_baseline"] = deltas

    maximize = spec.objective == "completed_jobs_per_hour"
    feasible = [result for result in (baseline, *alternatives) if result["feasible"]]
    direction = -1 if maximize else 1
    ordered = sorted(feasible, key=lambda result: (direction * result["objective_value"], result["name"]))
    rankings = []
    previous_value = None
    for position, candidate in enumerate(ordered, start=1):
        value = candidate["objective_value"]
        rank = rankings[-1]["rank"] if rankings and value == previous_value else position
        rankings.append({"rank": rank, "name": candidate["name"], "objective_value": value})
        previous_value = value

    trace = [job.model_dump(mode="json") for job in scenario.jobs]
    return {
        "report_schema_version": 1,
        "scenario_schema_version": scenario.schema_version,
        "search_schema_version": spec.schema_version,
        "source": scenario.source,
        "seconds_per_tick": scenario.seconds_per_tick,
        "trace_jobs": len(trace),
        "trace_sha256": canonical_hash(trace),
        "model": {
            "service_times": "fixed per job",
            "placement": "pack",
            "scope": (
                "Whole interchangeable GPUs, with configured topology affecting placement feasibility. "
                "The search models no hardware speed differences, cross-leaf runtime penalty, or measured performance."
            ),
            "mean_wait_population": "completed jobs only",
        },
        "objective": {"metric": spec.objective, "direction": "maximize" if maximize else "minimize"},
        "constraints": spec.constraints.model_dump(mode="json"),
        "baseline": baseline,
        "alternatives": alternatives,
        "feasible_rankings": rankings,
        "best_candidates": [result["name"] for result in rankings if result["rank"] == 1],
        "status": "ranked" if rankings else "no_feasible_candidate",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="Replay scenario defining the baseline and shared trace")
    parser.add_argument("search", type=Path, help="Versioned objective, constraints and candidate configurations")
    args = parser.parse_args()
    try:
        scenario_data = args.scenario.read_bytes()
        search_data = args.search.read_bytes()
        scenario = Scenario.model_validate_json(scenario_data)
        spec = SearchSpec.model_validate_json(search_data)
        report = search_configurations(scenario, spec)
        report.update(
            scenario_sha256=hashlib.sha256(scenario_data).hexdigest(),
            search_sha256=hashlib.sha256(search_data).hexdigest(),
            **git_provenance(),
        )
        print(json.dumps(report, indent=2, allow_nan=False))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
