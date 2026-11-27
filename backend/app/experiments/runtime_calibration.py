"""Fit and evaluate a single-GPU batch-latency model on held-out settings."""

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from pathlib import Path
from statistics import linear_regression, mean, median
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, StringConstraints, model_validator

MODEL_VERSION = "single-gpu-batch-latency-linear-v1"
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
BatchSize = Annotated[StrictInt, Field(gt=0, le=2**31 - 1)]
LatencyMs = Annotated[FiniteFloat, Field(gt=0, strict=True)]


class CalibrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BenchmarkProvenance(CalibrationInput):
    kind: Literal["published_measurements", "local_measurements", "synthetic_fixture"]
    publisher: Name
    source: Name
    revision: Name
    source_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")] | None = None
    setup: Name
    scope: Name


class Measurement(CalibrationInput):
    hardware: Name
    batch_size: BatchSize
    latency_ms: LatencyMs


class Benchmark(CalibrationInput):
    schema_version: Literal[1]
    workload: Name
    measurement: Literal["mean_single_gpu_batch_latency_ms"]
    provenance: BenchmarkProvenance
    holdout_batch_sizes: Annotated[tuple[BatchSize, ...], Field(min_length=1)]
    measurements: Annotated[tuple[Measurement, ...], Field(min_length=3)]

    @model_validator(mode="after")
    def validate_settings(self) -> "Benchmark":
        holdout = set(self.holdout_batch_sizes)
        if len(holdout) != len(self.holdout_batch_sizes):
            raise ValueError("holdout batch sizes must be unique")
        sizes_per_hardware: dict[str, set[int]] = defaultdict(set)
        for observation in self.measurements:
            settings = sizes_per_hardware[observation.hardware]
            if observation.batch_size in settings:
                raise ValueError(f"duplicate observation for {observation.hardware} at batch {observation.batch_size}")
            settings.add(observation.batch_size)
        for hardware, settings in sizes_per_hardware.items():
            training = settings - holdout
            if not holdout.issubset(settings) or len(training) < 2:
                raise ValueError(f"{hardware} must contain all holdout batches and at least two training settings")
            if min(holdout) < min(training) or max(holdout) > max(training):
                raise ValueError(f"{hardware} holdout batches must lie within the training range")
        return self


@dataclass(frozen=True)
class GpuBatchModel:
    slope_ms_per_item: float
    intercept_ms: float
    min_batch_size: int
    max_batch_size: int

    def predict_ms(self, batch_size: int) -> float:
        if type(batch_size) is not int or not self.min_batch_size <= batch_size <= self.max_batch_size:
            raise ValueError(f"batch size must be within [{self.min_batch_size}, {self.max_batch_size}]")
        duration = self.intercept_ms + self.slope_ms_per_item * batch_size
        if not isfinite(duration) or duration <= 0:
            raise ValueError("linear model produced an invalid duration")
        return duration


@dataclass(frozen=True)
class FittedRuntime:
    workload: str
    hardware_profiles: dict[str, GpuBatchModel]

    def predict_ms(self, workload: str, hardware: str, batch_size: int, *, placement: str = "single_gpu") -> float:
        if workload != self.workload:
            raise ValueError(f"unsupported workload: {workload!r}")
        if placement != "single_gpu":
            raise ValueError(f"unsupported placement: {placement!r}")
        if hardware not in self.hardware_profiles:
            raise ValueError(f"unsupported hardware: {hardware!r}")
        return self.hardware_profiles[hardware].predict_ms(batch_size)


def error_metrics(rows: list[dict], prediction: str) -> dict:
    signed_errors = [row[prediction] - row["measured_ms"] for row in rows]
    absolute_errors = [abs(error) for error in signed_errors]
    return {
        "settings": len(rows),
        "mae_ms": mean(absolute_errors),
        "rmse_ms": sqrt(mean(error**2 for error in signed_errors)),
        "mape_pct": 100 * mean(error / row["measured_ms"] for error, row in zip(absolute_errors, rows)),
        "bias_ms": mean(signed_errors),
        "observed_signed_error_ms": [min(signed_errors), max(signed_errors)],
        "max_absolute_error_ms": max(absolute_errors),
    }


def calibrate(benchmark: Benchmark) -> tuple[FittedRuntime, dict]:
    observations: dict[str, list[Measurement]] = defaultdict(list)
    for observation in benchmark.measurements:
        observations[observation.hardware].append(observation)

    models = {}
    slices = {}
    rows = []
    for hardware, values in sorted(observations.items()):
        sorted_values = sorted(values, key=lambda observation: observation.batch_size)
        training = [observation for observation in sorted_values if observation.batch_size not in benchmark.holdout_batch_sizes]
        batch_sizes = [observation.batch_size for observation in training]
        latencies_ms = [observation.latency_ms for observation in training]
        slope, intercept = linear_regression(batch_sizes, latencies_ms)
        model = GpuBatchModel(slope, intercept, min(batch_sizes), max(batch_sizes))
        # Checking both endpoints checks positivity throughout the supported linear interval.
        model.predict_ms(model.min_batch_size)
        model.predict_ms(model.max_batch_size)
        models[hardware] = model
        baseline = median(latencies_ms)
        holdout_rows = [
            {
                "hardware": hardware,
                "batch_size": observation.batch_size,
                "measured_ms": observation.latency_ms,
                "prediction_ms": model.predict_ms(observation.batch_size),
                "fixed_prediction_ms": baseline,
            }
            for observation in sorted_values
            if observation.batch_size in benchmark.holdout_batch_sizes
        ]
        slices[hardware] = {
            "training_batch_sizes": batch_sizes,
            "model": asdict(model),
            "fixed_baseline_ms": baseline,
            "model_errors": error_metrics(holdout_rows, "prediction_ms"),
            "fixed_baseline_errors": error_metrics(holdout_rows, "fixed_prediction_ms"),
        }
        rows.extend(holdout_rows)

    runtime = FittedRuntime(benchmark.workload, models)
    return runtime, {
        "report_schema_version": 1,
        "benchmark_schema_version": benchmark.schema_version,
        "model_version": MODEL_VERSION,
        "workload": benchmark.workload,
        "measurement": benchmark.measurement,
        "provenance": benchmark.provenance.model_dump(mode="json"),
        "method": "Ordinary least squares per hardware, compared with that hardware's training-only fixed median latency.",
        "holdout_batch_sizes": sorted(benchmark.holdout_batch_sizes),
        "hardware_slices": slices,
        "overall": {
            "model_errors": error_metrics(rows, "prediction_ms"),
            "fixed_baseline_errors": error_metrics(rows, "fixed_prediction_ms"),
        },
        "holdout_predictions": rows,
        "uncertainty": "Observed held-out error range only. Aggregate settings do not provide run-level variation or a prediction interval.",
        "unsupported": [
            "Different workloads, precision or software setups",
            "Other hardware profiles and extrapolation beyond training batch ranges",
            "Multi-GPU, cross-node or cross-leaf placement",
            "GPU sharing, co-location interference and production queueing",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path, help="Versioned measured benchmark JSON")
    args = parser.parse_args()
    try:
        data = args.benchmark.read_bytes()
        benchmark = Benchmark.model_validate_json(data)
        _, report = calibrate(benchmark)
        report["benchmark_sha256"] = hashlib.sha256(data).hexdigest()
        print(json.dumps(report, indent=2, allow_nan=False))
    except (OSError, ValueError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
