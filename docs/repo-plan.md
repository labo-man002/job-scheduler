# Slurm Observability - Repo Bootstrap Plan

## Working Decisions
- **Repo name:** `slurm-observability`
- **Visibility:** private for now
- **Repo model:** monorepo
- **First milestone:** `Milestone 1 - MVP Foundation and Hero Surface Runway`
- **Current merge request:** `docs: add MVP architecture, snapshot contract, and milestone 1 plan`
- **Next implementation focus:** establish the semantic spine that unblocks backend, frontend, and platform work in parallel

## First Merge Request Scope
The first MR should stay intentionally small and clean.

### Include
- `README.md`
- `docs/mvp-doc.md`
- minimal backend scaffold
- minimal frontend scaffold
- `deploy/` placeholder
- `fixtures/` placeholder
- `.gitignore`
- only the minimum config needed to establish the repo structure credibly

### Do not include
- fake features
- bloated boilerplate
- premature CI/CD complexity
- fake architecture code with no semantic value
- overbuilt production deployment setup

## Labels
Start with a small label set:
- `mvp`
- `backend`
- `frontend`
- `design`
- `semantics`
- `env`
- `docs`

## Milestone 1 Issue Set

### 1. Bootstrap monorepo skeleton
**Goal:** create the minimal repository structure and documentation baseline for the MVP.

**Why it matters:** gives the project a clean starting point without fake implementation bulk.

**Deliverables:**
- monorepo structure exists
- README exists
- MVP doc is included under docs
- backend/frontend minimal scaffolds exist
- basic dev config exists

**Checklist:**
- [ ] create top-level repo structure
- [ ] add `README.md`
- [ ] add `docs/mvp-doc.md`
- [ ] add backend skeleton
- [ ] add frontend skeleton
- [ ] add deploy/fixtures placeholders
- [ ] add `.gitignore`
- [ ] keep first commit intentionally minimal

**Out of scope:**
- real feature implementation
- CI/CD complexity
- production deployment

### 2. Stand up Slurm Docker reference environment
**Goal:** define and run the first real Slurm Docker cluster used as the MVP reference environment.

**Why it matters:** keeps the project grounded in real scheduler behavior instead of mock theater.

**Deliverables:**
- reference environment chosen
- setup documented
- environment runs locally
- available Slurm truth sources are inspected

**Checklist:**
- [ ] choose the reference Slurm Docker cluster repo/setup
- [ ] document local setup steps
- [ ] run the cluster successfully
- [ ] verify access to `squeue`, `sinfo`, `scontrol`, and/or `slurmrestd`
- [ ] inspect available topology/GRES truth
- [ ] record environment limitations and assumptions

**Out of scope:**
- production-grade deployment
- multi-cluster support

### 3. Define normalized backend domain model v1
**Goal:** define the canonical internal entities and relationships used by the MVP backend.

**Why it matters:** prevents raw Slurm structures from leaking everywhere and gives the product a stable semantic core.

**Deliverables:**
- domain model v1 documented
- entity boundaries clear
- source vs derived entities clearly separated

**Checklist:**
- [ ] define `Cluster`
- [ ] define `Partition`
- [ ] define `Node`
- [ ] define `Allocation`
- [ ] define `Job`
- [ ] define `User`
- [ ] define `TopologyGroup`
- [ ] define `Snapshot`
- [ ] decide treatment of `ResourceUnit / GRESUnit`
- [ ] document relationships between canonical entities
- [ ] document derived views vs source entities

**Out of scope:**
- fully generic future topology model
- premature support for all custom hardware layouts

### 4. Implement cluster overview API
**Goal:** expose the first normalized overview surface for the operator UI.

**Why it matters:** proves the first end-to-end path from scheduler truth to useful UI state.

**Deliverables:**
- cluster overview endpoint exists
- partition summaries exist
- queue summary exists
- basic utilization and pressure summaries exist

**Checklist:**
- [ ] define response schema
- [ ] expose cluster identity and freshness
- [ ] expose partition summaries
- [ ] expose queue summary
- [ ] expose basic utilization summary
- [ ] expose pressure/scarcity highlights
- [ ] add fixture/example response

**Out of scope:**
- deep drilldowns
- full historical analytics

### 5. Implement topology surface normalized API
**Goal:** expose the normalized topology/resource surface used by the hero screen.

**Why it matters:** this is the product’s visual backbone.

**Deliverables:**
- topology surface response shape exists
- grouped topology/resource structure exists
- allocation overlays are exposed
- overlay inputs exist for occupancy/fragmentation/pressure

**Checklist:**
- [ ] define topology surface response schema
- [ ] expose topology groups
- [ ] expose nodes/resources in grouped form
- [ ] expose allocation overlays
- [ ] expose selection/filter-ready identifiers
- [ ] expose overlay inputs for occupancy
- [ ] expose overlay inputs for fragmentation/pressure
- [ ] add fixture/example response

**Out of scope:**
- 3D mode
- fully generic graph layout system

### 6. Build hero UI shell and layout
**Goal:** create the first coherent operator surface in the frontend.

**Why it matters:** turns backend semantics into an actual usable product surface.

**Deliverables:**
- top summary bar
- left filter/queue panel
- center topology surface container
- right drilldown panel
- bottom insights panel
- shared selection/filter state model

**Checklist:**
- [ ] create app shell
- [ ] implement top summary bar
- [ ] implement left panel scaffold
- [ ] implement center topology surface scaffold
- [ ] implement right drilldown scaffold
- [ ] implement bottom insights scaffold
- [ ] define selection state model
- [ ] define filter state model
- [ ] support cross-panel state flow

**Out of scope:**
- polished final visuals
- advanced animation
- 3D interaction

### 7. Implement allocation drilldown and placement summary v1
**Goal:** make allocations first-class in the UI and expose placement meaningfully.

**Why it matters:** this is one of the main differentiators from generic Slurm dashboards.

**Deliverables:**
- allocation drilldown exists
- placement summary exists
- topology footprint is understandable from the UI

**Checklist:**
- [ ] define allocation drilldown schema
- [ ] expose associated job/user context
- [ ] expose occupied nodes/resources
- [ ] implement placement summary v1 semantics
- [ ] render placement summary in right panel
- [ ] support topology ↔ drilldown cross-highlighting

**Out of scope:**
- fully optimized placement scoring
- theoretical optimality judgments

### 8. Implement queue explanation + fragmentation/scarcity v1
**Goal:** provide the first semantic explanation layer that makes the tool genuinely useful to operators.

**Why it matters:** this is where the product becomes more than a dashboard.

**Deliverables:**
- queue explanation v1 exists
- fragmentation view v1 exists
- scarcity/pressure view v1 exists
- insights appear in backend and UI

**Checklist:**
- [ ] define queue explanation v1 semantics
- [ ] define fragmentation v1 semantics
- [ ] define scarcity/pressure v1 semantics
- [ ] implement derived backend logic
- [ ] expose derived views in API
- [ ] render first insights in UI
- [ ] validate explanations against reference environment behavior

**Out of scope:**
- perfect scheduler-decision reconstruction
- research-grade universal fragmentation metrics
