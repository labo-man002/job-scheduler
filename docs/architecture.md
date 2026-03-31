# Slurm Observability - MVP Architecture

## Goal
Build an observability-first Slurm operator tool that makes cluster state legible through normalized current state, topology-aware views, allocation visibility, and derived explanations for fragmentation and pending jobs.

## Product Boundary
The MVP is a read-oriented operator surface.

### In scope
- current cluster state ingestion
- normalized backend domain model
- topology/resource visualization
- allocation overlays
- queue and placement visibility
- first derived semantics for fragmentation, scarcity, and pending explanations
- lightweight recent snapshots/history

### Out of scope for MVP
- full control-plane mutation workflows
- user job submission UX
- provisioning/orchestration of clusters
- multi-cluster federation
- deeply generalized topology graph modeling
- 3D-first visualization

## Architectural Principle
The backend should ship meaning, not only facts.

That means:
- adapters stay thin
- normalization creates the canonical product model
- derived semantics live in the backend
- the frontend renders and explores normalized state rather than reconstructing scheduler meaning from raw Slurm output

## High-Level Components

### 1. Ingestion adapters
Responsible for acquiring scheduler and topology/resource truth.

Potential sources:
- `sinfo`
- `squeue`
- `scontrol`
- `slurmrestd`
- minimal auxiliary metadata where Slurm-native truth is insufficient for useful operator topology grouping

Constraints:
- source-specific code should stay narrow
- raw upstream formats should not define internal product semantics

### 2. Domain normalization layer
Responsible for converting raw source data into canonical internal entities.

Core entities:
- Cluster
- Partition
- TopologyGroup
- Node
- Job
- Allocation
- Snapshot

This layer defines the product's stable internal truth.

### 3. Derived semantics layer
Responsible for computing operator-facing meaning from normalized state.

Initial semantic surfaces:
- cluster summary
- placement summary
- queue explanation
- fragmentation summary
- scarcity / pressure summary
- lightweight recent deltas

This is the differentiation layer.

### 4. API layer
Responsible for serving UI-oriented surfaces.

Initial surfaces:
- cluster overview
- topology surface
- job drilldown
- allocation drilldown
- node/resource drilldown
- recent snapshot/history summaries

### 5. Frontend operator surface
Responsible for:
- rendering the hero screen
- linked interaction across queue, topology, drilldowns, and insights
- selection/filter state
- cross-highlighting

The frontend should not own core scheduling/resource interpretation logic.

## Runtime Shape
For MVP, keep the system simple:
- one backend service
- one frontend application
- one local/dev deployment path
- one reference Slurm environment

Avoid premature microservice decomposition.

## Reference Data Flow
1. Poll Slurm state
2. Normalize into canonical entities
3. Compute derived semantic summaries
4. Persist lightweight snapshot/history data
5. Serve UI-oriented API responses
6. Render linked operator views in the frontend

## Why this shape fits the team

### Khalil
Owns:
- domain model
- Slurm ingestion/normalization
- fragmentation/placeability semantics
- pending explanation logic
- API contracts

### Web developer
Owns:
- web shell and interaction model
- topology/grid surface
- drilldown UX
- queue/detail panels
- rendering and state composition

### Cloud/DevOps engineer
Owns:
- local/dev stack
- packaging and deployment
- CI/CD
- replay/demo environments
- environment consistency and observability

This split works best if the backend contracts are defined early and mock/replay snapshots exist from the start.

## Near-Term Architectural Deliverables
Milestone 1 should establish:
- the canonical snapshot contract
- the first normalized ingestion path
- the first mock/replay fixtures
- the first overview/topology API shapes
- the first hero UI shell
- the first issue/ownership breakdown for parallel work
