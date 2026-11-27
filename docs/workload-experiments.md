# Workload experiments

Open **Replay** in the running dashboard. Start with the two-GPU oracle, keep its cluster configuration and run the comparison. FIFO and Priority receive the same arrivals, GPU requests and service durations. The expected outcome is a useful installation check. Both finish at tick 14 with 27 of 28 GPU-ticks occupied. High-priority waiting falls from 11 to 3 ticks, while low-priority waiting rises from 4 to 5 ticks.

Open the saved result, give it a recognizable name and reload the page. Use the saved run as the starting point for another experiment, change capacity and run it again. Select both records in history to compare configurations. Examine completed jobs and unserved demand alongside average wait. A smaller mean among completed jobs can conceal work that never ran. For a scheduling-policy comparison, hold the cluster fixed. For a configuration comparison, hold the workload and queue policy fixed.

| Capability | Review reference | What the result establishes |
| --- | --- | --- |
| Import historical jobs | [Slurm accounting import #103](https://github.com/labo-man002/job-scheduler/issues/103) | A declared accounting window and inventory can be translated into replay inputs. Recorded durations alone cannot predict speed on different hardware. |
| Save and reuse experiments | [Persistence #105](https://github.com/labo-man002/job-scheduler/issues/105), [comparison #107](https://github.com/labo-man002/job-scheduler/issues/107) | A saved snapshot preserves the inputs and outputs for later inspection. Use synthetic or approved data on shared instances. |
| Compare network layouts | [Fabric #108](https://github.com/labo-man002/job-scheduler/issues/108), [example scenario](../examples/queue-replay/leaf-spine.json) | Reachability can change feasible placements. Fabric feasibility alone cannot quantify training speed. |
| Estimate workload runtime | [Calibration #109](https://github.com/labo-man002/job-scheduler/issues/109) | Evaluate predictions on held-out measurements within the documented benchmark domain. |
| Evaluate candidate configurations | [Bounded search #110](https://github.com/labo-man002/job-scheduler/issues/110) | A recommendation applies to the candidate set, objective, constraints and service assumptions used for the experiment. |
| Check practical scale | [Measured operating envelope](replay-scale-benchmark.md) | Measurements describe specific workloads and hardware. Re-run the benchmark for another environment. |

The [queue replay specification](queue-policy-replay.md) defines the event order and the oracle. The [milestone tracker](https://github.com/labo-man002/job-scheduler/issues/106) links the delivery dependencies.

See [Slurm baseline and cohort export](slurm-baseline-replay.md) and [runtime calibration and configuration search](calibration-and-search.md) for runnable commands and reference results.
