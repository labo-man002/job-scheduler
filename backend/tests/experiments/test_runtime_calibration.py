from pathlib import Path

import pytest

from app.experiments.runtime_calibration import Benchmark, calibrate

ROOT = Path(__file__).resolve().parents[3]
PUBLISHED = ROOT / "examples" / "runtime-calibration" / "nvidia-resnet50-amp-latency.json"


def make_benchmark(holdout_latency=22):
    return Benchmark.model_validate(
        {
            "schema_version": 1,
            "workload": "fixture-amp",
            "measurement": "mean_single_gpu_batch_latency_ms",
            "provenance": {
                "kind": "synthetic_fixture",
                "publisher": "test",
                "source": "test",
                "revision": "test",
                "setup": "deterministic algebraic fixture",
                "scope": "not measured",
            },
            "holdout_batch_sizes": [2],
            "measurements": [
                {"hardware": "fixture", "batch_size": 1, "latency_ms": 12},
                {"hardware": "fixture", "batch_size": 2, "latency_ms": holdout_latency},
                {"hardware": "fixture", "batch_size": 3, "latency_ms": 24},
            ],
        }
    )


def test_holdout_never_changes_fit_or_fixed_baseline():
    model, report = calibrate(make_benchmark())
    modified_model, modified_report = calibrate(make_benchmark(100))
    assert model == modified_model
    assert model.predict_ms("fixture-amp", "fixture", 2) == 18
    assert report["hardware_slices"]["fixture"]["fixed_baseline_ms"] == 18
    assert modified_report["hardware_slices"]["fixture"]["fixed_baseline_ms"] == 18
    assert report["overall"]["model_errors"]["observed_signed_error_ms"] == [-4, -4]
    assert modified_report["overall"]["model_errors"]["mae_ms"] == 82


def test_benchmark_rejects_missing_and_extrapolated_holdout_settings():
    benchmark = make_benchmark().model_dump()
    with pytest.raises(ValueError, match="all holdout batches"):
        Benchmark.model_validate({**benchmark, "holdout_batch_sizes": [4]})
    with pytest.raises(ValueError, match="within the training range"):
        Benchmark.model_validate({**benchmark, "holdout_batch_sizes": [3]})


def test_runtime_declines_unmeasured_scope():
    model, _ = calibrate(make_benchmark())
    with pytest.raises(ValueError, match="unsupported workload"):
        model.predict_ms("other", "fixture", 2)
    with pytest.raises(ValueError, match="unsupported hardware"):
        model.predict_ms("fixture-amp", "other", 2)
    with pytest.raises(ValueError, match="unsupported placement"):
        model.predict_ms("fixture-amp", "fixture", 2, placement="cross_leaf")
    with pytest.raises(ValueError, match="batch size"):
        model.predict_ms("fixture-amp", "fixture", 4)


def test_pinned_published_benchmark_report():
    model, report = calibrate(Benchmark.model_validate_json(PUBLISHED.read_bytes()))
    assert report["provenance"]["kind"] == "published_measurements"
    assert report["holdout_batch_sizes"] == [4, 16, 64, 128]
    assert report["overall"]["model_errors"]["settings"] == 8
    assert report["overall"]["model_errors"]["mae_ms"] == pytest.approx(3.4132, abs=0.001)
    assert report["overall"]["fixed_baseline_errors"]["mae_ms"] == pytest.approx(23.515)
    assert model.hardware_profiles.keys() == {"T4", "V100-16GB"}
