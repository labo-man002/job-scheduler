# Architecture

Design history lives in issues [#25](https://github.com/taroryu004-lab/job-scheduler/issues/25)–[#27](https://github.com/taroryu004-lab/job-scheduler/issues/27). This is the current agreed shape.

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
        +topology: Topology
        +place(job) Node
        +release_resource(node) None
        #filter_nodes(nodes, job) list~Node~
        #reserve_resource(node) None
    }

    class PlaceAlgorithm {
        <<interface>>
        +select(candidates, job, view) Node
    }
    class PackAlgorithm {
        +select(candidates, job, view) Node
    }
    class SpreadAlgorithm {
        +select(candidates, job, view) Node
    }

    class Cluster {
        +cluster_id: int
        +cluster_name: str
        +topology_type: TopologyType
        +dimension: list~int~
        +wrap: bool
    }

    class Topology {
        +cluster: Cluster
        +build_view(nodes) TopologyView
    }

    class TopologyView {
        +neighbors(node) list~Node~
        +distance(a, b) int
    }

    class Node {
        +node_id: int
        +status: NodeStatus
        +cluster: Cluster
        +coordinates: list~int~
        +resources: list~ResourceNode~
        +free_resources(resource_type) list~ResourceNode~
    }

    class ResourceNode {
        +resource_type: ResourceType
        +resource_type_index: int
        +status: ResourceStatus
    }

    class AllocationRepository {
        +save(allocation) Allocation
        +find_by_job_id(job_id) Allocation
        +delete(allocation_id) None
    }

    class Allocation {
        +alloc_id: int
        +resource_nodes: list~ResourceNode~
        +job: Job
        +begin_time: datetime
        +duration_minutes: int
        +status: AllocationStatus
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
    Placer "1" --> "1" Topology : uses
    Topology "1" --> "1" Cluster : configured by
    Topology ..> TopologyView : builds
    PlaceAlgorithm ..> TopologyView : traverses
    Placer "1" o-- "*" Node : manages
    Cluster "1" --> "*" Node : hosts
    Node "1" *-- "1..*" ResourceNode : has
    Server "1" --> "1" AllocationRepository : uses
    AllocationRepository "1" --> "*" Allocation : stores
    Allocation "1" --> "1..*" ResourceNode : spans
    Allocation "1" --> "1" Job : for
    Client "1" --> "*" Job : submits
    Job "1" *-- "1..*" ResourceRequest : requires
```

## How the pieces fit together

- **`Client`** builds a `Job` itself and calls `submit_job(job)` / `cancel_job(job_id)` / `get_allocation_details(job_id)` — currently maintained commands.
- **`Server`** is the boundary: it's the only thing a `Client` talks to. It assigns `job_id`/`owner` on receipt (so a client can't forge either), forwards jobs to `Scheduler`, and is the only class that reads/writes `AllocationRepository`.
- **`Scheduler`** only decides *when* a job gets handled: it orders the queue (`SortStrategy` — `PrioritySort` or `FifoSort`, swappable), and calls `Placer` to attempt placement. It doesn't build or store allocations.
- **`Placer`** only decides *where*: it filters candidate `Node`s and delegates the actual pick to a `PlaceAlgorithm` (`PackAlgorithm` or `SpreadAlgorithm`, swappable). It returns which node's `ResourceNode` units get consumed.
- **`Allocation`** is where the request side (`Job`) and the resource side (`ResourceNode`) meet — it holds the specific `ResourceNode` units consumed, not a single `Node`, since one allocation can span several resource units (or several nodes). It's built by `Server` after a successful placement and persisted through `AllocationRepository`, backed by the database described in [docs/erd.md](erd.md).

### Where vs. when

The two classes that make an allocation happen are split by exactly one question each:

- **`Scheduler` answers *when*.** Given the queue, whose turn is it? That's ordering — `SortStrategy` (`PrioritySort` or `FifoSort`) decides, and it's swappable independently of everything else.
- **`Placer` answers *where*.** Given a job whose turn has come, which node fits it? That's placement — `PlaceAlgorithm` (`PackAlgorithm` or `SpreadAlgorithm`) decides, also swappable independently.

Neither one needs to know how the other makes its decision — `Scheduler` just calls `Placer.place(job)` once a job reaches the front of the queue.

### Topology

A `Node` belongs to exactly one `Cluster`, and its position is a `coordinates` vector rather than a fixed `(x, y, z)` — the vector's length matches the cluster's dimensionality. `Cluster` carries `topology_type` (e.g. `TORUS`, `MESH`, `TREE`, `FLAT` — see [docs/erd.md](erd.md)), `dimension` (the size of each axis, so `[8, 8, 8]` describes what used to be the only supported shape: a fixed 3D torus), and `wrap` (whether coordinates wrap at each axis's boundary — `wrap=true` is what makes a topology a torus instead of a plain grid). `Topology` is the runtime object built from a `Cluster`'s config; given the current node population, it builds a `TopologyView` — a fresh, disposable snapshot with `neighbors(node)` and `distance(a, b)` that a `PlaceAlgorithm` traverses to make its pick.

The reason it's split into `Topology` + `TopologyView` rather than one object: `Pack`/`Spread` need to reason about occupancy — "which free candidate is closest to an already-`OCCUPIED` node" — and occupied nodes never appear in `candidates` (they failed the resource-fit filter). Only `Placer` has the full node list, so `Placer` is the one holding `topology` and calling `topology.build_view(self.nodes)` before every placement attempt; `PlaceAlgorithm.select(candidates, job, view)` then traverses that view without needing any state of its own.

- **`PackAlgorithm`** walks `view` from the candidates toward the nearest `OCCUPIED` node and picks the closest, consolidates usage, keeps free space contiguous.
- **`SpreadAlgorithm`** does the same walk and picks the farthest.

Both algorithms rely on `neighbors`/`distance` being defined generically over `coordinates`, `dimension`, and `wrap` rather than hardcoded 3D math — that's what makes them work unchanged whether the cluster is a torus, a mesh, or something else. Grid dimensions used to be fixed config with a single implied cluster; now they're data on `Cluster`, and more than one cluster (each with its own topology) is representable.

**Resolved (issue #27, 2026-08-01 "final agreed on version"):** the `Cluster` entity proposed on 2026-07-29 is now designed — see [docs/erd.md](erd.md) and [docs/decisions.md](decisions.md) for what it looks like and what's still open (e.g. whether one `Placer` handles multiple clusters or there's one `Placer` per cluster).
