# Job Scheduler

A job scheduling and placement system: a client submits a job, a scheduler orders the queue, a placer assigns the job to a node, and the resulting allocation is tracked in a database.

Built with **FastAPI** (backend) and **TypeScript** (frontend). Design history lives in issues #25–#27.

## Status

Design phase. The design in [docs/](docs/) is the current agreed shape; implementation scaffolding is starting in `backend/` and `frontend/`.

## Documentation

- [docs/architecture.md](docs/architecture.md) — class diagram and how the pieces (`Client`, `Server`, `Scheduler`, `Placer`, `Topology`, `Allocation`, ...) fit together.
- [docs/erd.md](docs/erd.md) — database schema backing persistence.
- [docs/decisions.md](docs/decisions.md) — assumptions and modeling decisions behind both of the above, plus open items.
