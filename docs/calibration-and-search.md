# Runtime calibration and bounded configuration search

Run from the repository root with the backend dependencies installed.

## Fit a measured latency model

```sh
PYTHONPATH=backend python -m app.experiments.runtime_calibration \
  examples/runtime-calibration/nvidia-resnet50-amp-latency.json > /tmp/calibration.json
```

The input records 18 published single-GPU mean batch latencies for ResNet50 v1.5 mixed-precision inference on a V100 16 GB and a T4. Its provenance names the source table, revision, file digest and setup. Five batch sizes per device fit a linear latency model with ordinary least squares. The other four batch sizes per device evaluate interpolation. Across the eight held-out settings, mean absolute error is **3.41 ms**, compared with **23.52 ms** for a constant per-device training median. The JSON includes individual errors, device-level summaries and the split so a reader can inspect where the model misses. [NVIDIA benchmark](https://github.com/NVIDIA/DeepLearningExamples/blob/5843f4e5a1220dd98936e477d8597d8a77320666/PyTorch/Classification/ConvNets/resnet50v1.5/README.md#inference-performance-results)

These published averages support a narrow comparison across batch sizes. Replicate-level variation, training, concurrent tenants, collectives and cross-node placement remain unmeasured. The queue replay and search use the durations specified in their input jobs. They do not apply this latency model to arbitrary jobs.

## Search a declared candidate set

```sh
PYTHONPATH=backend python -m app.experiments.configuration_search \
  examples/queue-replay/oracle.json examples/configuration-search/spec.json > /tmp/rankings.json
```

The spec names one objective, limits and up to 32 alternatives. Each can change queue policy, node capacity and fabric. All candidates receive the same jobs in the same order. Returned rows expose the complete cluster configuration, constraint violations, unscheduled jobs, per-class waits and metric deltas from the baseline.

In the bundled oracle, the four-GPU FIFO candidate completes at tick 9. The two-GPU baseline and Priority tie at tick 14. The one-GPU and disconnected candidates both leave work unserved and violate the zero-unscheduled constraint. The result identifies the best feasible candidate in this list. It gives no estimate of operating cost, GPU generation speedup or production workload performance.
