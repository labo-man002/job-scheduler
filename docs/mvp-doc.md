# Slurm Observability MVP - Working Draft

## 1. Project Summary
- Open-source, observability-first operating surface for Slurm clusters.
- Primary users: cluster admins / operators.
- Secondary users: infra / runtime / platform engineers working on complex scheduling and resource systems.
- Long-term differentiator: topology-aware scheduling visibility, placement understanding, fragmentation insight, and custom topology support.

## 2. Problem Statement
Existing cluster tooling is fragmented and weak at presenting a coherent operational picture of:
- queue state
- allocation state
- utilization
- fragmentation
- topology
- resource ownership / who is using what and when

The MVP should unify this into one operator-facing surface.

## 3. Product Thesis
Build an operator-first Slurm observability UI that makes cluster state legible by combining:
- topology-aware resource views
- allocation overlays
- queue context
- utilization / fragmentation insight
- placement-aware operational visibility

## 4. Product Direction
- Open-source first.
- Generic Slurm first.
- Start from topologies already known/managed by Slurm.
- Layer in custom topology support later as a differentiator.
- Focus on operator usefulness before broad workflow coverage.

## 5. Non-Goals for MVP
The MVP should **not** attempt to:
- replace Slurm
- become the full control plane for everything
- handle full cluster provisioning
- provide user job submission flows
- boil the ocean with every admin/user workflow
- over-invest in 3D rendering before the core operator surface is useful

## 6. Primary MVP User Questions
The MVP should help operators understand not just scheduler state, but scheduler consequences.
It should explain why jobs are pending, where jobs are placed, how current allocations shape fragmentation and backfill opportunity, who is consuming scarce resources, and why a cluster that appears free may still be operationally hard to schedule efficiently.

### Queue reasoning
Operators should be able to answer:
- Why is this job pending?
- What exact constraint is blocking placement?
- Is the blocker capacity, topology fit, partition policy, reservation, or scheduling order?
- Which currently running allocations are shaping this outcome?

### Placement visibility
Operators should be able to answer:
- Where did this job land?
- Why did it land there?
- How contiguous or scattered is the placement?
- Is the placement topology-efficient or merely feasible?
- What locality tradeoff was effectively made?

### Fragmentation visibility
Operators should be able to answer:
- Where is free capacity fragmented?
- What kinds of requests are now harder to place because of current allocations?
- How much apparently free capacity is not meaningfully usable for a given class of jobs?
- What parts of the cluster are operationally stranded?

### Backfill visibility
Operators should be able to answer:
- Where is backfill currently possible?
- What jobs could be scheduled opportunistically?
- What capacity is idle but temporarily usable?
- What future placement pressure might make today’s opportunistic choices costly?

### Ownership and scarcity visibility
Operators should be able to answer:
- Who is using scarce resources?
- What users/jobs dominate constrained regions of the topology?
- Which allocations are lightweight vs heavyweight in placement terms?
- What is consuming the most operationally valuable capacity?

### Cluster legibility
Operators should be able to answer:
- What is actually happening in the cluster right now?
- What is healthy / overloaded / blocked / fragmented / drained?
- What changed recently?
- Where should I look first?

## 7. Hero MVP Screen
The hero MVP screen is a live, topology-aware operator surface centered on a grouped 2D cluster/resource map with allocations overlaid.
It should connect queue state, placement state, occupancy, fragmentation, and resource ownership in one coherent interaction loop.
Operators should be able to scan the cluster, identify pressure or anomalies, select jobs/nodes/allocations/users, and immediately understand the scheduling and placement consequences of the current cluster state.

### Core layout

#### Center: topology/resource surface
The main visual core should show:
- grouped node/resource tiles
- partition/rack/group structure where meaningful
- current allocations overlaid
- state colors for free / allocated / drained / down / problematic capacity
- optional highlighting for selected jobs, users, allocations, fragmentation hotspots, and backfill opportunity zones

#### Cluster / queue summary
A compact summary area should show:
- pending vs running jobs
- partition pressure
- high-level free/used/down capacity
- important pending reasons
- enough context to tell whether the operator should focus on queue pressure or topology state first

#### Context / drilldown panel
When an operator selects something, the UI should explain it.
Examples:
- job → owner, requested resources, state, pending reason or placement, allocated region/resources
- node → partition, resources, allocations, node state
- user → active jobs, occupied resources, topology footprint
- allocation → shape, placement locality, resource occupancy

#### Derived insight panel
A supporting panel should expose a first useful layer of derived insight, such as:
- fragmentation indicators
- utilization summaries
- backfill opportunities
- recent changes / lightweight history

### Core interaction loop
The hero screen should support this loop:
1. See cluster shape
2. Notice an issue or anomaly
3. Select a job / node / allocation / user
4. Read an explanation
5. Understand the scheduling and placement consequence
6. Decide what to investigate or do next

### What to avoid
The hero screen should avoid:
- chart clutter
- raw Slurm dumps pretending to be UX
- premature 3D gimmicks
- unclear visual encodings
- mixing status and analytics so heavily that the screen becomes hard to scan

## 8. MVP Scope
### Must-have
- Cluster overview
- Queue summary
- Live topology/resource view
- Allocation overlays
- Drilldown for jobs / nodes / users / allocations
- Basic utilization view
- Basic fragmentation / placement insight
- Lightweight recent state history / snapshots

### Explicitly later
- User submission / request flows
- Full config-from-UI
- Deep RBAC complexity
- Multi-cluster federation
- Billing/accounting
- Advanced 3D visualization as core product surface

## 9. UI Direction
### Overall structure
- Linked hybrid operator view
- Strongest visual core: 2D grouped tile/grid topology surface
- Supporting panels for:
  - queue
  - allocation details
  - resource details
  - filters
  - analytics

### Why 2D first
- readability
- density
- operational clarity
- better labels and overlays
- faster product iteration
- avoids building a beautiful but weak operator toy

### Later UI expansion
- graph-like topology views where useful
- 3D mode only if it adds actual operational insight

## 10. Domain Entities
The MVP domain model should distinguish between **canonical operational entities** and **derived interpretation views**.

### Canonical entities
- **Cluster** — top-level monitored Slurm environment
- **Partition** — scheduler-facing grouping boundary
- **Node** — core schedulable infrastructure unit
- **ResourceUnit / GRESUnit** — explicit schedulable resource layer where needed for placement visibility
- **Job** — scheduler-facing workload object
- **Allocation** — actual occupied resource footprint associated with a job
- **User** — ownership / operator context object
- **TopologyGroup** — hierarchical grouping layer for topology-aware rendering and reasoning
- **Snapshot** — lightweight persisted recent-state summary

### Derived views
- **PlacementView** — computed summary of how an allocation maps onto topology
- **FragmentationView** — computed view of stranded / difficult-to-use free capacity
- **QueueExplanationView** — operator-facing explanation of why work is pending or constrained
- **ScarcityView** — computed summary of where operationally valuable capacity is under pressure

### Key relationships
- Cluster contains partitions and topology groups
- Partitions contain or reference nodes
- Nodes expose resources / GRES units
- Jobs belong to users
- Jobs produce or reference allocations
- Allocations occupy nodes and/or resource units
- Nodes and resource units belong to topology groups
- Snapshots summarize cluster / partition / queue / allocation state at time T
- Placement, fragmentation, queue explanation, and scarcity views are derived from the operational state model

### Key modeling principle
The UI should render allocations and placement consequences, not just jobs.
Allocation should therefore be treated as a first-class entity in the product model.

### Topology modeling principle
MVP topology modeling should begin from Slurm-managed or Slurm-known structure and remain hierarchical-first, with richer graph/custom-topology semantics added later.

## 11. Reference Environment
- First real environment: Slurm Docker cluster
- Not mock-only
- MVP should stay grounded in real scheduler behavior from early on

## 12. Data / Ingestion Strategy
The MVP operates on two main classes of truth.

### Scheduler truth
Derived from Slurm-managed state, including:
- jobs
- queue state
- pending reasons
- partitions
- nodes
- allocation-relevant scheduler metadata

### Resource / topology truth
Derived from Slurm-managed topology/resource information first, especially:
- nodes
- grouping structure
- GRES-backed resources
- any minimal additional metadata needed to make placement and topology legible

The MVP should prefer existing Slurm interfaces first and use `slurmrestd` where it provides cleaner or more structured access, without tightly coupling the internal model to one ingestion path.
The first implementation should normalize upstream data into a stable backend domain model rather than leaking raw Slurm structures directly into the UI.

### Initial approach
- Use existing Slurm interfaces first
- Use `slurmrestd` where useful
- Prefer Slurm-managed topology/resource truth wherever possible
- Add only the minimum external topology metadata needed to make placement meaningfully visible

### MVP update model
- Poll current scheduler/resource state periodically
- Maintain a normalized current-state view
- Persist lightweight recent snapshots for short-horizon historical views

### MVP derived data
The backend should compute an initial useful set of derived views, such as:
- occupancy summaries
- placement summaries
- fragmentation indicators
- scarcity views
- queue explanation rollups
- allocation overlays mapped onto topology structure

### Evolution path
- Start with a lightweight ingestion layer over existing Slurm interfaces
- Gradually move toward a normalized backend / sidecar
- Let the backend become the semantic layer joining:
  - scheduler truth
  - topology truth
  - derived analytics

## 13. Architecture Direction
The system should be designed around a normalized internal domain model rather than raw Slurm APIs or UI-specific convenience structures.

### Ingestion adapters
Thin source-specific adapters for:
- Slurm interfaces
- `slurmrestd`
- topology/resource metadata sources

These adapters should remain narrow and should not define the product’s semantics.

### Domain normalization
A canonical internal model for scheduler and topology/resource state, including entities such as:
- clusters
- partitions
- nodes
- jobs
- allocations
- GRES resources
- topology groups
- normalized current-state snapshots

### Derived analytics / explanation layer
A backend semantic layer should compute the first useful operational interpretations of cluster state, including:
- placement summaries
- fragmentation indicators
- scarcity views
- queue explanation rollups
- occupancy summaries
- recent state deltas

### API layer
The API should be oriented around operator use cases and UI interaction needs, rather than simply exposing backend tables or mirroring raw upstream formats.

### Frontend presentation layer
The frontend should be responsible for:
- rendering
- interaction
- drilldown
- linked views
- presentation composition

The frontend should **not** be responsible for inferring core scheduling/resource semantics from raw source data if the backend can provide that meaning explicitly.

### Architectural principle
The backend should ship meaning, not only facts.

### MVP temporal model
- normalized current live state
- lightweight recent snapshots for short-horizon history

### Backend responsibilities
- ingest Slurm state
- ingest topology/resource metadata
- normalize domain entities
- derive utilization / fragmentation / placement views
- expose API for the UI

### Frontend responsibilities
- render topology/resource state clearly
- provide drilldowns and linked views
- present scheduler/resource state in a legible way without becoming the hidden analytics engine

### What to avoid
- tight coupling to a single Slurm interface
- raw Slurm structures leaking into UI contracts
- frontend-owned analytics logic
- premature microservices
- premature event-stream complexity
- over-generalizing topology before one good supported topology model exists

### Evolution path
Start with a lightweight monolithic backend and clear internal boundaries.
Evolve toward a more explicit sidecar/semantic backend only as product complexity and integration demands justify it.

## 14. Suggested MVP Stack
### Backend
- Python
- FastAPI

### Frontend
- React
- TypeScript

### Storage
- PostgreSQL

### Updates
- polling first
- websocket push where useful later

### Deployment
- Docker Compose

## 15. Why This Project Has an Edge
Unique advantage behind the project:
- topology-aware scheduling understanding
- understanding of the scheduling / placement feedback loop
- ability to model resource geometry and operational consequences, not just generic dashboards

## 16. Open-Source Strategy
Open source should help with:
- credibility
- contributor attraction
- operator adoption
- reputation / portfolio strength
- potential future business wedge

## 17. First Demo Story
Show:
- a cluster
- the queue
- a pending job
- current allocations
- fragmentation / placement state
- why a cluster that looks free may still not be effectively placeable

The demo should prove this is an operational explanation tool, not just a pretty dashboard.

## 18. MVP Success Criteria
The MVP should primarily prove **operator usefulness**, and secondarily prove **technical feasibility**.

### Operator usefulness
The MVP is successful if an operator can:
- understand current cluster state quickly
- explain why a job is pending
- understand where and how a job/allocation was placed
- identify fragmentation and operationally stranded capacity
- understand where backfill may be possible
- identify who is consuming scarce resources

### Legibility / UX
The MVP is successful if:
- the hero screen is coherent and readable
- topology, queue, and allocation state feel unified rather than fragmented
- drilldowns clarify operational state instead of exposing raw scheduler clutter
- the UI makes scheduler/resource consequences easier to reason about than standard Slurm surfaces

### Technical credibility
The MVP is successful if:
- it runs against a real Slurm Docker cluster
- it ingests live scheduler state reliably enough for the operator surface
- it maintains a normalized current-state model
- it supports lightweight recent snapshots/history
- it can drive the hero demo without hidden manual stitching

### Product integrity
The MVP is successful if it remains a focused, observability-first operator tool rather than drifting into an early all-in-one control plane.

## 19. Open Questions
### Environment / source questions
- What exact Slurm interfaces should be used first in MVP v1?
- Where should `slurmrestd` be preferred over CLI adapters?
- What is the exact first Slurm Docker cluster reference environment?
- What topology and GRES structure does that environment actually expose?

### Domain model questions
- What is the first supported topology abstraction from Slurm-managed topology?
- How explicit should `ResourceUnit / GRESUnit` be in v1?
- What is the minimum useful allocation model?
- What should be persisted in snapshots vs derived on demand?

### Analytics / explanation questions
- How should fragmentation be defined for the first supported resource model?
- What is the first useful placement summary?
- What is the first useful queue explanation beyond raw pending reasons?
- How should scarcity/pressure be measured meaningfully for operators?
- What is the first backfill-opportunity explanation model?

### UI / workflow questions
- What are the minimum filters required for usefulness?
- What are the minimum drilldowns required for credibility?
- What is the first visual grouping strategy for the reference cluster?
- How much lightweight history is enough for MVP?

### Product boundary questions
- What exact workflows remain out of scope for MVP?
- What signals would justify expanding into submission, control-plane, or richer admin workflows later?

## 20. Next Steps
1. Lock the MVP product cut:
   - operator-first
   - observability-first
   - no submission/control-plane expansion yet
   - first demo story centered on queue + allocation + fragmentation explanation

2. Lock the first reference environment:
   - define the exact Slurm Docker cluster setup
   - inspect available topology/GRES truth
   - identify the first supported topology/resource abstraction

3. Define the first backend domain contracts:
   - canonical entities
   - allocation model
   - topology group model
   - snapshot model

4. Define the first derived-semantics contracts:
   - fragmentation v1
   - placement summary v1
   - queue explanation v1
   - scarcity/pressure summary v1

5. Define the first API surface:
   - cluster overview
   - topology surface
   - allocation drilldown
   - job drilldown
   - recent snapshot/history summaries

6. Bootstrap the implementation skeleton:
   - backend
   - adapters
   - normalized state model
   - storage/snapshots
   - frontend shell

7. Build the first hero-screen path end-to-end using the real Slurm Docker cluster.

## 21. MVP Semantics
### Fragmentation v1
Fragmentation in MVP v1 is defined as the loss of effective placeability caused by the distribution of free capacity across topology/resource space.
A cluster may have substantial free capacity in aggregate while still being operationally fragmented if that capacity no longer forms usable placement shapes for important request classes.

Fragmentation v1 should be expressed through:
- spatial visibility of fragmented free regions
- request-fit degradation for representative placement classes
- concise operator-facing explanation of why free capacity is harder to use than raw totals suggest

### Placement summary v1
Placement summary in MVP v1 is a topology-aware explanation of an allocation’s resource footprint.

It should describe:
- where the allocation landed
- what topology groups/resources it spans
- whether the placement is compact or scattered
- whether the placement is topology-coherent or merely feasible
- what operational tradeoff the placement implies

Placement summary should help operators reason about the consequences of current allocations, not just inspect raw job-to-node assignments.

### Queue explanation v1
Queue explanation in MVP v1 should go beyond raw Slurm pending reasons and provide an operator-facing interpretation of why a job is pending.

It should connect:
- scheduler-reported reason
- dominant blocking constraint class
- required placement/resource shape
- relevant occupancy/fragmentation/scarcity context

The goal is not to perfectly reproduce every scheduler decision path, but to make pending state operationally legible.

### Scarcity / pressure v1
Scarcity / pressure in MVP v1 should identify where operationally valuable capacity is constrained relative to demand.

It should not be treated as a synonym for raw utilization.
Instead, it should highlight:
- scarce resource classes
- pressured topology regions
- limited high-quality placement shapes
- concentrated demand on operationally important capacity

The goal is to help operators see where the cluster is strategically tight, not merely where it is numerically busy.

## 22. MVP API Surface
The MVP API should be organized around operator use cases and hero-screen interaction flows rather than mirroring raw backend tables or upstream Slurm formats.

### Cluster overview
A cluster overview surface should return:
- cluster identity / summary
- partition summaries
- queue summary
- global utilization summary
- scarcity/pressure highlights
- lightweight recent snapshot summary

This endpoint/view should power the first landing state of the operator UI.

### Topology surface
The topology surface should return the normalized visual state needed for the hero screen, including:
- topology groups
- nodes
- resources / GRES summaries where relevant
- allocation overlays
- state coloring inputs
- active highlights for fragmentation / pressure / selected filters

This should be a UI-oriented normalized view, not a direct dump of upstream scheduler data.

### Allocation drilldown
An allocation drilldown surface should return:
- allocation identity
- associated job and user
- occupied nodes/resources
- placement summary
- topology footprint
- basic resource occupancy
- relevant operator-facing note about placement consequence

### Job drilldown
A job drilldown surface should return:
- job identity
- owner
- requested resources
- current state
- pending reason or running placement linkage
- queue explanation
- associated allocation if running/placed

### Node / resource drilldown
A node/resource drilldown surface should return:
- node/resource identity
- state
- partition / topology group membership
- capacity summary
- active allocations/jobs
- local occupancy / pressure context

### Recent snapshot / history summaries
A recent snapshot/history surface should return lightweight short-horizon historical information such as:
- recent queue pressure changes
- recent utilization movement
- recent fragmentation shifts
- recent allocation/occupancy deltas

### API design principle
The API should ship meaning, not only facts.
It should return enough normalized and derived semantics that the frontend can render the operator model directly without re-inventing backend reasoning in the browser.

## 23. Hero Screen Wireframe / Interaction Model
### Screen zones
The MVP hero screen should be organized into a small number of stable zones.

#### Top summary bar
Should show:
- cluster identity
- timestamp / live freshness
- global queue summary
- high-level utilization / pressure indicators
- active alerts or notable operator-relevant signals

#### Left panel: filters and queue context
Should provide:
- partition filters
- state filters (pending / running / down / drain / etc.)
- user / job search or filter
- queue summary grouped by meaningful dimensions
- a compact list of important pending jobs or pressure sources

#### Center panel: topology/resource surface
This is the primary visual surface.
It should show:
- grouped 2D tile/grid topology representation
- nodes and resource groupings
- allocation overlays
- active overlay mode coloring
- selected-object highlighting
- cross-highlighting from filters and drilldowns

#### Right panel: drilldown context
Should display details for the current selection, such as:
- job details
- allocation details
- node/resource details
- user footprint details
- placement summary
- queue explanation

#### Bottom panel: derived insight / recent changes
Should expose:
- fragmentation signals
- scarcity / pressure signals
- lightweight recent history
- recent state changes relevant to the current view or selection

### Core UI state model
The hero screen should maintain explicit state for:
- selected job
- selected allocation
- selected node/resource
- selected user
- active partition / state / owner filters
- current overlay mode
- current topology grouping mode
- current time horizon for recent-history context

Only one primary drilldown target should be active at a time, but cross-highlighting may affect multiple objects.

### Overlay modes
The center topology surface should support a small number of high-value overlay modes, such as:
- occupancy
- allocations
- fragmentation
- scarcity / pressure
- placement quality (later, if useful)

The default mode should be whichever best supports operator scanning on first load, likely occupancy or allocations.

### Core interactions
The hero screen should support:
- hover → lightweight preview / highlight
- click → primary selection and right-panel drilldown
- filter → cross-highlight and partial re-focus
- selection from queue/job list → highlight topology footprint
- selection from topology → reveal job/allocation/user context
- switching overlay modes without losing core selection state

### Cross-highlighting behavior
The UI should make relationships visible across zones.
Examples:
- selecting a job highlights its allocation on the topology surface
- selecting an allocation highlights occupied nodes/resources and related job/user context
- selecting a user highlights that user’s active footprint
- selecting a fragmented region or pressure hotspot highlights the most relevant jobs/allocations if possible

### Interaction principle
The hero screen should let an operator move naturally through this loop:
1. scan current cluster shape
2. notice a problem or anomaly
3. select a job / node / allocation / user / region
4. understand the explanation in context
5. decide what to investigate next

### Wireframe principle
The hero screen should prioritize legibility and relationship clarity over feature count.
If a panel or interaction does not help the operator understand scheduler/resource consequences, it should not be part of the MVP hero surface.

## 24. Repo Structure / Implementation Plan
### Top-level repo structure
A first implementation could be organized as:
- `backend/` — ingestion, normalization, semantics, API, snapshots
- `frontend/` — operator UI
- `docs/` — MVP doc, notes, future design docs
- `deploy/` — Docker Compose, local/dev deployment assets
- `fixtures/` — sample normalized states, fake/test snapshots, UI fixture data

### Backend structure
A suggested backend layout:
- `backend/adapters/` — Slurm CLI adapters, `slurmrestd` adapters, topology metadata adapters
- `backend/domain/` — canonical entities and state model
- `backend/semantics/` — fragmentation, placement summary, queue explanation, scarcity logic
- `backend/api/` — FastAPI routes / schemas / response shaping
- `backend/storage/` — snapshots, persistence, retention logic
- `backend/services/` — orchestration and application-layer workflows

### Frontend structure
A suggested frontend layout:
- `frontend/src/app/` — app shell, routing, page layout
- `frontend/src/features/topology/` — topology surface and related UI logic
- `frontend/src/features/queue/` — queue panels and job context views
- `frontend/src/features/drilldown/` — right-panel selection/detail views
- `frontend/src/features/insights/` — fragmentation / pressure / recent changes panels
- `frontend/src/state/` — shared UI state and selection/filter state
- `frontend/src/components/` — shared presentation components

### Implementation boundaries
The implementation should preserve a few hard boundaries:
- adapters should stay thin
- domain model should stay canonical and upstream-independent
- semantics should live in the backend, not be recreated in the frontend
- API contracts should be use-case oriented
- frontend should consume normalized, meaningful surfaces rather than reconstructing backend reasoning

### Suggested execution milestones
#### M0 — Reference environment
- stand up the Slurm Docker cluster
- inspect actual exposed scheduler and topology/GRES truth
- define the first supported topology/resource abstraction

#### M1 — Ingestion + normalized current state
- implement first adapters
- normalize cluster / partition / node / job / allocation state
- expose a first internal current-state model

#### M2 — Cluster overview surface
- implement cluster overview API
- implement queue and partition summary views
- prove the basic end-to-end data path

#### M3 — Topology surface
- implement grouped 2D topology/resource surface
- render node/resource state and allocation overlays
- support basic filters and selection

#### M4 — Drilldowns + semantics
- add job drilldown
- add allocation drilldown
- add placement summary
- add queue explanation
- add first fragmentation / scarcity hints

#### M5 — Lightweight recent history
- persist snapshots
- expose recent deltas / pressure / utilization movement
- integrate recent-history context into the hero screen

#### M6 — First hero demo
- polish the operator flow
- support the first demo story end-to-end
- show a cluster, queue, pending job, allocation state, fragmentation context, and why apparently free capacity may still not be meaningfully placeable

### Implementation principle
The first implementation should optimize for:
- product truth
- semantic clarity
- real operator usefulness

It should not optimize first for:
- ultimate scalability
- full generality
- architectural cleverness for its own sake
