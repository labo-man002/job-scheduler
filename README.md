# slurm-observability

An operator-first, observability-first UI for Slurm clusters.

This project aims to make cluster state legible by combining:
- topology-aware resource views
- allocation overlays
- queue context
- placement visibility
- fragmentation and scarcity insight

## Status

Early MVP bootstrap.

## How We Work

We are building this as a focused, operator-first product — not as a generic Slurm dashboard, not as a portal clone, and not as a premature all-in-one control plane.

### Product standard
- Keep the wedge sharp: **make placeability legible**.
- Prioritize operator understanding of:
  - queue state
  - allocation shape
  - topology/resource state
  - fragmentation / scarcity
  - scheduler consequences
- Prefer useful explanation over raw data dumps.
- Prefer readable 2D operator workflows over flashy but weak visualization.

### Engineering standard
- Keep the backend as the semantic layer.
- Keep adapters thin and normalize upstream data early.
- Do not leak raw Slurm structures directly into the UI contract unless there is a strong reason.
- Use shared contracts and fixtures so backend, frontend, and demo work can move in parallel.
- Avoid premature architecture complexity; one solid backend + one solid frontend is enough for MVP.

### Team workflow
- **Khalil:** domain model, Slurm normalization, semantics, API contracts
- **Web:** frontend/operator surface, topology/grid UX, drilldowns, interaction design
- **Cloud/DevOps:** local/dev stack, containers/compose, CI/CD, replay/demo environment

### Execution rule
Before building new surfaces, make sure we can answer:
- what operator problem this solves
- what semantic contract it depends on
- whether it improves understanding of placement, fragmentation, or scheduler consequences

If it does not strengthen the core wedge, it is probably not MVP work.

See:
- `docs/mvp-doc.md`
- `docs/repo-plan.md`
- `docs/architecture.md`
- `docs/cluster-snapshot-v0.md`
- `docs/milestone-1.md`
- `docs/PROJECT_STATUS.md`
