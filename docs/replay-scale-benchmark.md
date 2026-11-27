# Replay scale benchmark (#111)

Measured on 27 November 2026. Python 3.12.14 on Linux x86-64, Intel Xeon Platinum 8573C, nine logical CPUs visible in the workspace. Each repeat starts a fresh Python process. Wall time covers both policy runs and excludes scenario parsing, interpreter startup and JSON encoding. Peak RSS is process high-water memory through result encoding, including imports and interpreter. Event and byte counts are for the complete pair of runs.

## Replay and report size

The generated windows repeat the checked-in contention workload's job shapes, priorities and arrival offsets every 16 virtual ticks. A four-node cluster has two GPUs per node. All jobs in these generated windows complete in both variants. This is a synthetic contention stress test. Actual Slurm workload distributions and measured counterfactual outcomes remain outside these windows.

| Jobs | Paired event count | Median replay (3 runs) | Peak RSS, max | Compact input JSON | Compact pair JSON |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 848 | 0.098 s | 50.1 MiB | 6,540 B | 89,325 B |
| 1,000 | 8,529 | 0.636 s | 57.5 MiB | 65,515 B | 913,450 B |
| 5,000 | 42,668 | 3.297 s | 88.5 MiB | 334,515 B | 4,658,191 B |

Median rate at 5,000 jobs was about 1,516 input jobs per wall-clock second, each replayed under both policies. For this layout and workload the results support an offline batch of at least 5,000 jobs on the measured environment. Treat that as the largest verified point. At web scale, exact event ledgers expose data transfer, JSONB storage and API serialization costs in addition to the simulator. Increasing cluster width, peak overlapping queue depth or event verbosity can change these costs. The compact pair payload counts per-job outcomes and ledgers. It excludes persisted metadata and the derived comparison.

A separate instrumented 5,000-job run spent 7.61 of 10.75 replay seconds in placement. Candidate-group selection accounted for 6.51 seconds, including reachability, locality and feasible-subset enumeration. Rebuilding transient ORM jobs accounted for 2.35 seconds. These are cumulative profiler times and are unsuitable for wall-time comparisons with the table. Prioritize profiling the placement path and remeasuring a wider workload before changing the algorithm.

## Reproduce

From the repository root with the backend's dependencies installed:

```bash
PYTHONPATH=backend python scripts/benchmark_replay.py --sizes 100 1000 5000 --repetitions 3 > /tmp/replay-benchmark.json
PYTHONPATH=backend python scripts/benchmark_replay.py --scenario examples/queue-replay/contention.json > /tmp/replay-fixture-benchmark.json
```

The output records samples, normalized input hash, environment and Git provenance. Supply `--scenario` to benchmark a compatible, shareable replay JSON window. Source labels are retained as supplied. To examine CPU hot spots separately, run the worker under `python -m cProfile`; profiler time should stay out of reported latency.

## Persisted history and detail

Measured on a fresh PostgreSQL 16.2 instance using the integrated worktree based at `ad43556`. Created 25 distinct 1,000-job paired runs and issued ten reads per endpoint.

| Operation | Samples | Median wall time | Min–max | Response bytes |
| --- | ---: | ---: | ---: | ---: |
| Create pair and persist | 25 | 737.2 ms | 665.4–888.2 ms | 1,206,437 |
| History, first 20 rows | 10 | 5.3 ms | 4.2–21.8 ms | 5,724 |
| Reopen saved detail | 10 | 33.1 ms | 31.3–39.9 ms | 1,206,437 |

The mean combined input/output JSONB footprint was 149,718 bytes per saved pair. The table, indexes and out-of-line storage totaled 4,063,232 bytes. The measured history page is compact; full results transfer over a megabyte for 1,000 jobs. Compression and response sizes are specific to the repeating workload.

Run the benchmark against a local disposable instance with PostgreSQL migrations applied. The URL is the API base. A fresh request ID seeds a separate stored pair per iteration. Use a fresh benchmark database to reproduce population size. The history request reads the first 20 newest summaries and the detail request reads one saved full snapshot, including both ledgers.

```bash
PYTHONPATH=backend python scripts/benchmark_replay.py --sizes 1000 --repetitions 3 \
  --api-url http://127.0.0.1:8000 --seed-runs 25 --history-reads 10 > /tmp/replay-persistence-benchmark.json
```

Measure elapsed wall time through the complete local HTTP response. The save path includes paired replay, transaction and response. History and detail include database lookup, API serialization and transport; these samples use warmed data in a local single-client run. The JSON includes response sizes and raw sample counts. The application-facing JSON sizes and PostgreSQL storage footprint differ because of metadata, JSONB and compression. Collect a PostgreSQL snapshot after the run for actual storage:

```sql
SELECT count(*) AS rows,
       round(avg(pg_column_size(inputs) + pg_column_size(outputs))) AS mean_snapshot_bytes,
       pg_total_relation_size('replay_runs') AS total_relation_bytes
FROM replay_runs;
```

History at higher cardinalities and concurrent write/read contention require separate measurements. Real historical replay needs a permission-safe accounting window, a matching inventory and a defensible baseline.
