# Queue policy replay

## Experiment specification

This is the first virtual-time experiment in the Job Scheduler roadmap. It asks how strict FIFO and strict priority change class-specific waiting times on the same small GPU cluster. Fixed synthetic service times isolate the effect of queue order.

One versioned JSON scenario specifies the tick length in seconds, source, node IDs and GPU counts, and jobs with IDs, arrival and service ticks, GPU demand, and priority. Each run gets fresh in-memory inventory. Both runs use the existing topology-aware Placer, Pack policy and linear coordinate topology. The replay uses the same ordering strategies as Scheduler and owns the event timing outside the API server.

At each tick, release all completed jobs, admit arrivals in input order, then dispatch repeatedly. A blocked queue head keeps its place among jobs of equal rank. A newly arrived higher-priority job can be considered first on the next dispatch opportunity under Priority. Jobs that cannot fit an empty cluster are reported separately. The run drains or reports any work that remains blocked when no events can make progress.

### Acceptance criteria

- Run both variants with one command and emit machine-readable provenance, per-job outcomes and event logs.
- The two-GPU oracle finishes at tick 14 in both variants and uses 27 of 28 GPU-ticks. Low-priority wait changes from 4 to 5 ticks. High-priority wait changes from 11 to 3 ticks.
- With all priorities equal, event and job outputs agree. Reversing the order of the policy runs yields the same report for each policy.
- Cover simultaneous releases and arrivals, stable ties after blocking, impossible demand, allocation across nodes, and exact capacity accounting.
- Report queue-class trade-offs with sample counts and an explicit denominator. Label synthetic data and fixed service times.

## Reproduce the experiment

Install `backend/requirements.txt` in your Python environment, then run these commands from the repository root.

```bash
PYTHONPATH=backend python -m app.experiments examples/queue-replay/oracle.json --output /tmp/queue-oracle.json
PYTHONPATH=backend python -m app.experiments examples/queue-replay/contention.json --output /tmp/queue-contention.json
```

The CLI needs no database service. It prints a comparison on stderr and writes JSON to the specified path or to stdout when `--output` is omitted. Use a clean Git checkout to associate the report with a committed source revision. The normalized trace and configuration hashes, time unit, event ledger, and allocation identities are included in the JSON.

## Results

| Scenario | Policy | Mean high-priority wait | Mean low-priority wait | Last completion tick | GPU occupancy |
| --- | --- | ---: | ---: | ---: | ---: |
| Two-GPU oracle | FIFO | 11 (1 job) | 4 (1 job) | 14 | 27/28 (96.4%) |
| Two-GPU oracle | Priority | 3 (1 job) | 5 (1 job) | 14 | 27/28 (96.4%) |
| Three-node contention | FIFO | 13.4 (5 jobs) | 11.33 (3 jobs) | 31 | 156/186 (83.9%) |
| Three-node contention | Priority | 2.6 (5 jobs) | 16.67 (3 jobs) | 33 | 156/198 (78.8%) |

The oracle isolates the redistribution of waiting time. On the three-node fixture, Priority lowers high-priority waits, raises low-priority waits and leaves more idle GPU-time over the run. Both policies complete 11 jobs and reject the same seven-GPU job on the six-GPU cluster.

Times are in fixture ticks. The occupancy denominator is total GPU capacity multiplied by elapsed virtual time from tick zero to the last completion. Class wait statistics use completed jobs and expose sample counts. Median and nearest-rank p95 are omitted below five and twenty observations, respectively. These examples use synthetic arrivals and fixed durations. They measure allocation and queue behavior under the specified policy rules. Workload performance, network contention, and production outcomes require measured data and validation.
