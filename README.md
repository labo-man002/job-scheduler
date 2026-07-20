# Workload Management System

A from-scratch workload management system: a client submits a job, a scheduler orders the queue, a placer assigns the job to a node, and the resulting allocation is tracked in a database.

Built with **FastAPI** (backend) and **TypeScript** (frontend). Design history lives in issues #25–#27.

## Status

Design phase. Class diagram below is the current agreed shape; implementation scaffolding is starting in `backend/` and `frontend/`.

## Class diagram

```mermaid
classDiagram
    direction TB

    class Client {
        +id: int
        +institute: str
        +connect() None
        +disconnect() None
        +submit_job(job) Job
        +cancel_job(job_id) None
        +get_allocation_details(job_id) Allocation
    }

    class Job {
        +job_id: int
        +owner: Client
        +priority: Priority
        +submitted_at: datetime
        +duration_minutes: int
        +status: JobStatus
        +requirements: list~ResourceRequest~
    }

    class ResourceRequest {
        +resource_type: ResourceType
        +amount: int
    }

    class Server {
        +scheduler: Scheduler
        +allocation_repository: AllocationRepository
        +submit_job(job) Job
        +cancel_job(job_id) None
        +get_allocation_details(job_id) Allocation
    }

    class Scheduler {
        +job_queue: Queue~Job~
        +placer: Placer
        +sort_strategy: SortStrategy
        +enqueue(job) None
        +dequeue() Job
        +remove(job_id) bool
        +attempt_placement(job) Node
        +release_node(node) None
    }

    class SortStrategy {
        <<interface>>
        +sort(queue) Queue~Job~
    }
    class PrioritySort {
        +sort(queue) Queue~Job~
    }
    class FifoSort {
        +sort(queue) Queue~Job~
    }

    class Placer {
        +nodes: list~Node~
        +algorithm: PlaceAlgorithm
        +place(job) Node
        +release_resource(node) None
    }

    class PlaceAlgorithm {
        <<interface>>
        +select(candidates, job) Node
    }
    class PackAlgorithm {
        +select(candidates, job) Node
    }
    class SpreadAlgorithm {
        +select(candidates, job) Node
    }

    class Node {
        +node_id: int
        +status: NodeStatus
        +resources: list~ResourceNode~
        +available_capacity() list~ResourceNode~
    }

    class ResourceNode {
        +resource_type: ResourceType
        +used_capacity: int
        +total_capacity: int
    }

    class AllocationRepository {
        +save(allocation) Allocation
        +find_by_job_id(job_id) Allocation
        +delete(allocation_id) None
    }

    class Allocation {
        +alloc_id: int
        +node: Node
        +job: Job
        +begin_time: datetime
        +duration_minutes: int
        +is_alive() bool
    }

    Client "1" --> "*" Job : submits
    Job "1" *-- "1..*" ResourceRequest : requires
    Client "1" --> "1" Server : connects to
    Server "1" --> "1" Scheduler : forwards to
    Scheduler "1" o-- "1" Placer : uses
    Scheduler ..> SortStrategy : uses
    SortStrategy <|.. PrioritySort
    SortStrategy <|.. FifoSort
    Placer ..> PlaceAlgorithm : uses
    PlaceAlgorithm <|.. PackAlgorithm
    PlaceAlgorithm <|.. SpreadAlgorithm
    Placer "1" o-- "*" Node : manages
    Node "1" *-- "1..*" ResourceNode : has
    Server "1" --> "1" AllocationRepository : uses
    AllocationRepository "1" --> "*" Allocation : stores
    Allocation "1" --> "1" Node : on
    Allocation "1" --> "1" Job : for
```

## How the pieces fit together

- **`Client`** builds a `Job` itself and calls `submit_job(job)` / `cancel_job(job_id)` / `get_allocation_details(job_id)` — three explicit commands rather than one generic entry point, so dispatch is just normal method resolution, no internal type-switch.
- **`Server`** is the boundary: it's the only thing a `Client` talks to. It assigns `job_id`/`owner` on receipt (so a client can't forge either), forwards jobs to `Scheduler`, and is the only class that reads/writes `AllocationRepository`.
- **`Scheduler`** only decides *when* a job gets handled: it orders the queue (`SortStrategy` — `PrioritySort` or `FifoSort`, swappable), and calls `Placer` to attempt placement. It doesn't build or store allocations.
- **`Placer`** only decides *where*: it filters candidate `Node`s and delegates the actual pick to a `PlaceAlgorithm` (`PackAlgorithm` or `SpreadAlgorithm`, swappable). It returns a `Node`, not an `Allocation`.
- **`Allocation`** is where the request side (`Job`) and the resource side (`Node`) meet. It's built by `Server` after a successful placement and persisted through `AllocationRepository`, backed by the database described in the issue #27 ER diagram.

## Open design questions

- **REST vs. WebSocket:** `Client.connect()`/`disconnect()` assume a persistent session. Plain REST has no connect step — identity comes from the request itself. Keep them only if live job/allocation status pushes are wanted.

## Layout

- `backend/` — FastAPI service
- `frontend/` — TypeScript client
