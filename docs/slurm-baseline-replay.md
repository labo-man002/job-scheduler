# Validate a Slurm accounting window

[Issue #103](https://github.com/labo-man002/job-scheduler/issues/103) compares observed Slurm allocations with one baseline replay before interpreting a policy change. The comparison conditions on completed single-attempt jobs with fixed recorded service times. Its time unit is one second and its cluster represents one to four nodes with interchangeable whole GPUs.

## Reproduce the fixture

Install `backend/requirements.txt`, then run this from the repository root.

```bash
PYTHONPATH=backend python -m app.experiments.slurm_baseline \
  examples/slurm-baseline/accounting.psv examples/slurm-baseline/inventory.json \
  --policy fifo --output /tmp/slurm-baseline.json
```

This is a synthetic 15-row accounting fixture with a synthetic inventory, a 30-second observation horizon, and six included allocation records. It models one carry-in running allocation, one carry-in waiting job, one later start outside the horizon, an array task, and missing or unsupported records. It deliberately produces discrepancies. Four matched starts have a mean absolute error of one second. Observed utilization is 52 of 60 allocated GPU-seconds and the replay has 56 of 60. The pointwise occupancy mean absolute error is 4/60. No production Slurm replay accuracy follows from the fixture.

## Prepare a real window

Select a dedicated cluster/partition slice whose jobs use only its dedicated, fixed inventory, with one whole-GPU type and a stable active node set. Exclude shared partitions, overlapping jobs from another partition, capacity changes and heterogeneous typed requests unless an operator can supply an equivalent isolated slice. Record the inventory independently of the job trace. GPU counts are usable device counts, not the highest count observed in accounting. In the snapshot template, `snapshot_at` should be at or before the left boundary and `accounting_captured_at` should be at or after the right boundary. Set `data_kind` to `measured` only for genuine data. Record the collection command and release in `trace_source`, and the independent snapshot method and slice assumptions in `inventory_source`. Fields `cluster` and `partition` select the same names in both files.

Export `sacct --parsable2` with its header, allocation and duplicate visibility, and no private account/user/job-name fields. The selected lookback must cover every job already waiting or running at the boundary. Include follow-up long enough to resolve completed durations for that cohort. Use operator snapshots and accounting reconciliation to check that the queried history includes all carry-in jobs and competing allocations. The importer has no independent way to prove coverage.

```bash
TZ=UTC SLURM_TIME_FORMAT=standard sacct --allusers --allocations --duplicates --parsable2 \
  --clusters YOUR_CLUSTER --partition YOUR_DEDICATED_PARTITION \
  --starttime LOOKBACK_START_UTC --endtime FOLLOWUP_END_UTC \
  --format 'JobID%128,JobIDRaw%128,Cluster%64,Partition%64,Submit,Eligible,Start,End,ElapsedRaw,State%64,Restarts,Suspended,ReqTRES%1024,AllocTRES%1024,Priority,Reservation%128' \
  > /tmp/accounting.psv
```

Available fields, accounting permissions and record selection can vary by Slurm release and site settings. Check the export against `sacct --helpformat`, the site’s boundary snapshots, and any missing or truncated rows. Use timestamps in UTC when they omit an offset. Explicit offsets are converted to UTC. Keep stable job and node pseudonyms when sharing an approved export. [SchedMD sacct reference](https://slurm.schedmd.com/sacct.html)

### Import and boundary rules

| Input | Baseline interpretation |
|---|---|
| Identity | Keeps display `JobID` and `JobIDRaw`, including numeric array tasks. Filters step rows and ambiguous duplicate identities. Grouped array placeholders and heterogeneous job component IDs are unsupported. |
| Availability | Uses `Eligible` for policy arrival and retains `Submit` separately. Missing eligibility is reported and has no submit-time fallback. The deterministic replay orders eligible ties by numeric raw identity, then display identity. |
| GPU count | Replays requested GPUs from `ReqTRES` and measures allocation from `AllocTRES`. Excludes mismatches. Generic plus typed counts represent the same allocation and are never added together. Typed counts require the declared inventory GPU type. GPU sharing, GPUs with a different type, and unsupported state histories have explicit exclusions. |
| Priority | Inventory specifies strictly increasing minimum recorded Slurm priorities for LOW, NORMAL, HIGH, and URGENT. They apply to the recorded value. Static replay classes cannot reproduce Slurm’s evolving priority, and defaults are specific to the fixture. |
| Service | Uses `ElapsedRaw` for fixed service once confirmed by `End - Start`. Suspensions, requeues, and explicitly reserved jobs are excluded. Observed starts initialize only already-running jobs. The simulator receives eligibility, request, priority class and service duration for other jobs. |
| Carry-in | With `Start < window_start < End`, reserve the recorded aggregate quantity at the left boundary and release it at the recorded end. With `Eligible < window_start <= Start`, place the job in the queue at the boundary while retaining its original eligibility time. At the right boundary, clip occupancy to the half-open horizon. |
| Censoring | A known follow-up completion permits service-duration use even when the end is censored within the comparison window. A start at or after the right boundary has no measured in-window wait. Pending or running jobs without supported service durations are excluded and counted, even if they might alter contention. Incomplete coverage is flagged. |
| Hardware placement | Boundary placement reserves equivalent whole GPUs against aggregate capacity. Exact historical GPU and node assignments, changing topology, and contention beyond GPU counts are outside this experiment. A carry-in whose aggregate GPUs exceed capacity invalidates the baseline. |

### Interpret the report

Both occupancy series cover the same half-open horizon and selected cohort. Occupancy integrates `allocated GPUs × seconds`, with capacity times observed seconds as the denominator. It is allocation occupancy rather than device compute utilization. Inspect time-weighted occupancy error and its interval ledger in addition to the signed aggregate error. Opposing shifts can cancel in the aggregate. A report with unsupported or missing competing allocations only represents the selected, reconstructable subset.

Starts are paired only when both timelines start the same job in the observation horizon. Carry-in starts are prior observations and excluded from start-error scoring. The report includes paired signed and absolute errors, class-level observed/simulated/paired eligible waits, largest discrepancies, unpaired starts, and counts. Empirical nearest-rank p95 on small samples is descriptive. Reasons for discrepancies remain hypotheses until joined with supporting Slurm evidence such as current policy, resource constraints, or job reasons. Backfill, fair-share, queue priority updates, reservations, node constraints, and job/runtime interactions may explain differences in real data.

The JSON includes both input hashes, source notes, and checkout provenance when available. Keep raw accounting and output outside the repository unless the operator has approved sharing. The committed example contains only synthetic data. A real isolated trace with a matching independent inventory is still needed to establish fidelity against Slurm production behavior.
