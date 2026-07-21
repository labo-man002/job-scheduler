# Job Scheduler

A from-scratch job scheduling and placement system: a client submits a job, a scheduler orders the queue, a placer assigns the job to a node, and the resulting allocation is tracked in a database.

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
    Client "1" --> "*" Job : submits
    Job "1" *-- "1..*" ResourceRequest : requires
```

## How the pieces fit together

- **`Client`** builds a `Job` itself and calls `submit_job(job)` / `cancel_job(job_id)` / `get_allocation_details(job_id)` — currently maintained commands.
- **`Server`** is the boundary: it's the only thing a `Client` talks to. It assigns `job_id`/`owner` on receipt (so a client can't forge either), forwards jobs to `Scheduler`, and is the only class that reads/writes `AllocationRepository`.
- **`Scheduler`** only decides *when* a job gets handled: it orders the queue (`SortStrategy` — `PrioritySort` or `FifoSort`, swappable), and calls `Placer` to attempt placement. It doesn't build or store allocations.
- **`Placer`** only decides *where*: it filters candidate `Node`s and delegates the actual pick to a `PlaceAlgorithm` (`PackAlgorithm` or `SpreadAlgorithm`, swappable). It returns on which allocated `Node`.
- **`Allocation`** is where the request side (`Job`) and the resource side (`Node`) meet. It's built by `Server` after a successful placement and persisted through `AllocationRepository`, backed by the database described in the issue #27 ER diagram.

### Where vs. when

The two classes that make an allocation happen are split by exactly one question each:

- **`Scheduler` answers *when*.** Given the queue, whose turn is it? That's ordering — `SortStrategy` (`PrioritySort` or `FifoSort`) decides, and it's swappable independently of everything else.
- **`Placer` answers *where*.** Given a job whose turn has come, which node fits it? That's placement — `PlaceAlgorithm` (`PackAlgorithm` or `SpreadAlgorithm`) decides, also swappable independently.

Neither one needs to know how the other makes its decision — `Scheduler` just calls `Placer.place(job)` once a job reaches the front of the queue.

## Database schema

The ER diagram backing `AllocationRepository` (and the rest of the persisted state), tracked in issue #27. `priority`, `job_status`, `node_status`, and `resource_type` are lookup tables — the relational equivalent of the enums in the class diagram above.

```mermaid
erDiagram
    client {
        int id PK
        string institute
    }

    priority {
        int id PK
        string name
    }

    job_status {
        int id PK
        string name
    }

    resource_type {
        int id PK
        string name
    }

    job {
        int job_id PK
        int owner_id FK
        int priority_id FK
        int status_id FK
        datetime submitted_at
        int duration_minutes
    }

    job_requirement {
        int id PK
        int job_id FK
        int resource_type_id FK
        int amount
    }

    node_status {
        int id PK
        string name
    }

    node {
        int node_id PK
        int status_id FK
    }

    node_resource {
        int id PK
        int node_id FK
        int resource_type_id FK
        int used_capacity
        int total_capacity
    }

    allocation {
        int alloc_id PK
        int node_id FK
        int job_id FK
        datetime begin_time
        int duration_minutes
    }

    client ||--o{ job : submits
    priority ||--o{ job : categorizes
    job_status ||--o{ job : categorizes
    job ||--|{ job_requirement : requires
    resource_type ||--o{ job_requirement : "is a"
    node_status ||--o{ node : categorizes
    node ||--|{ node_resource : has
    resource_type ||--o{ node_resource : "is a"
    node ||--o{ allocation : hosts
    job ||--|| allocation : "results in"
```

Three corrections from the original issue #27 diagram: `node_resource.node_id` is the FK (not `node.resource_node_id`), so one node can carry several resource rows; `duration_minutes` is an `int`, not a `timestamp` — a duration is a length, not a point in time; and `allocation` no longer carries `client_id` — the owner is reachable through `job.owner_id`.

