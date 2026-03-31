# PROJECT_STATUS.md — slurm-observability

## Purpose
This file is the fast-reload project memory for future sessions.
Read this early before making project decisions, opening PRs, or planning work.

## Project Identity
- **Repo:** `slurm-observability`
- **Local path:** `/data/.openclaw/workspace/slurm-observability`
- **GitHub:** `taroryu004-lab/slurm-observability`
- **Positioning:** operator-first, topology-aware observability surface for Slurm clusters

## Core Product Wedge
The project is **not** meant to be just another Slurm dashboard, Grafana clone, or Open OnDemand-style portal.

The core wedge is to make these things legible together:
- queue state
- allocation shape
- topology/resource state
- fragmentation / placeability
- scarcity / pressure
- operator-facing explanations of scheduler consequences

Pinned internal rule:
> We are not trying to build just another Slurm UI.
> We are trying to build the surface that explains scheduler/resource consequences better than existing tools do.

## Current Direction
The MVP is:
- **observability-first**
- **operator-first**
- **read-oriented**
- grounded in a **real Slurm reference environment**

### MVP in scope
- current cluster state ingestion
- normalized backend domain model
- topology/resource visualization
- allocation overlays
- queue and placement visibility
- first derived semantics for fragmentation, scarcity, and pending explanations
- lightweight recent snapshots/history

### Explicitly not in scope for MVP
- full control-plane mutation workflows
- user job submission UX
- provisioning/orchestration of clusters
- multi-cluster federation
- deeply generalized topology graph modeling
- 3D-first visualization

## Team Shape
- **Khalil:** domain model, Slurm ingestion/normalization, semantics, API contracts
- **Web friend:** frontend/operator surface, topology/grid UX, drilldowns, filters, interaction composition
- **Cloud/DevOps friend:** environment setup, containers/compose, CI/CD, local/dev stack, demo/replay support

## Architecture Direction
The intended MVP architecture is:
- one backend service
- one frontend application
- one local/dev deployment path
- one reference Slurm environment

Guiding principle:
- adapters stay thin
- normalization creates canonical product truth
- derived semantics live in backend
- frontend renders and explores normalized meaning instead of reconstructing scheduler semantics itself

## Shared Contract Direction
The first major shared contract is **ClusterSnapshot v0**.
It is meant to support:
- mock fixture driven UI development
- replayable demo scenarios
- live Slurm-backed current-state rendering

Key entities in the contract:
- Cluster
- Partition
- TopologyGroup
- Node
- Job
- Allocation
- ClusterSummary
- FragmentationSummary
- PendingAnalysisSummary

This contract is important because it is the semantic spine that lets backend, frontend, and demo work proceed in parallel.

## Important Existing Docs
Read these before doing serious project work:
- `README.md`
- `docs/mvp-doc.md`
- `docs/repo-plan.md`
- `docs/architecture.md`
- `docs/cluster-snapshot-v0.md`
- `docs/milestone-1.md`
- `notes/positioning-note.md`

## GitHub State Already Created
These already exist and should be treated as project reality, not suggestions.

### Pull request
- **PR #16**
- Title: `docs: add MVP architecture, snapshot contract, and Milestone 1 plan`

### Milestone
- **Milestone 1 - MVP Foundation and Hero Surface Runway**

### Milestone 1 issues
- #17 Stand up Slurm Docker reference environment
- #18 Define normalized backend domain model v1
- #19 Implement ClusterSnapshot v0 contract and fixture set
- #20 Implement cluster overview API
- #21 Implement topology surface normalized API
- #22 Build hero UI shell and layout
- #23 Implement allocation drilldown and placement summary v1
- #24 Implement queue explanation and fragmentation/scarcity v1

## Near-Term Priority Order
The current recommended order is:
1. architecture + snapshot contract
2. fixtures + replay mode
3. reference environment + backend normalization
4. overview/topology API surfaces
5. hero UI shell
6. derived explanation/fragmentation layer

## Operational Reminder For Future Sessions
Before acting, remember:
- the repo already exists and has pushed work
- the project direction is already narrowed
- do not treat `/data/.openclaw/workspace` as the repo root for this project
- use `/data/.openclaw/workspace/slurm-observability`
- read the project docs first when resuming work
- preserve momentum by anchoring decisions to the existing wedge: placeability, fragmentation, topology, allocation consequences

## Current Best Next Steps
The highest-leverage next implementation moves are:
- represent `ClusterSnapshot v0` in code
- create first fixture scenarios
- set up replay-driven development
- stand up the reference Slurm Docker environment
- start the normalized backend domain model and overview API
