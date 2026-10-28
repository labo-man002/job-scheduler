# Job Scheduler — canonical technical glossary

This glossary is the shared vocabulary for the job scheduler's domain model, runtime scheduling, placement, and GPU-network research. Its purpose is to prevent one term from silently acquiring two meanings in code review or design discussion.

**Canonical hardware hierarchy:** one `Cluster` contains `Node` objects, and each `Node` contains `ResourceNode` records. A **Node is a physical compute server**. This is the agreed terminology for [#94](https://github.com/labo-man002/job-scheduler/issues/94); it does **not** introduce an additional persistent `PhysicalServer` entity.

The Python `Server` class is a software application service, **not** a physical server. The leaf-spine prototype's `GpuServer` is a network-facing wrapper referring to an existing `Node`, **not** another owner of GPUs. Whether that wrapper should remain after integration is unresolved ([#87](https://github.com/labo-man002/job-scheduler/issues/87), [#93](https://github.com/labo-man002/job-scheduler/issues/93)).

## How to read this document

Each entry includes a definition, the code or document that currently owns the concept, and an example or non-equivalence. Status means:

- **Live:** implemented in the active scheduling/allocation path.
- **Prototype:** implemented in the standalone in-memory leaf-spine module, not connected to live placement.
- **Concept:** explanatory infrastructure term, not necessarily modeled in the application.
- **Proposed:** an intended architectural rule or interface not implemented end to end.
- **Open:** a decision requiring explicit resolution. Do not treat it as a current invariant.

Names in backticks refer to exact Python symbols where available. Ordinary terms such as *physical server* describe domain concepts. If source code, an older diagram, and this glossary disagree about **current behavior**, verify the main-branch code and tests, then record the inconsistency; do not silently reinterpret the implementation. For **intended design**, record the decision in [`decisions.md`](decisions.md) before describing it as settled.

### Ownership in one example

```text
Cluster "training-a" (one selected cluster-level topology)
  ├── Node 41 (one physical compute server)
  │     ├── ResourceNode: GPU device 0
  │     ├── ResourceNode: GPU device 1
  │     └── ResourceNode: CPU unit 0
  └── Node 42 (another physical compute server)
        └── ResourceNode: GPU device 0
```

The example is illustrative, not a seeded database fixture. `ResourceNode` rows have per-node resource-type indices and their own allocation states. A count such as “2 free GPUs on Node 41” is **derived** from those units; it is not maintained separately by `GpuServer`.

## 1. Core hardware and resource identities

| Term | Canonical definition and ownership | Code reference | Example / important distinction | Status |
| --- | --- | --- | --- | --- |
| **`Server`** | Request-scoped application service coordinating admission, cluster selection, scheduling, persistence, and resource release. | [`domain/server.py`](../backend/app/domain/server.py) | `Server._build_placer()` loads and locks nodes. It is **not** a rack or compute host. | Live |
| **Physical compute server** | One host that contributes allocatable resources to a cluster; canonically represented by `Node`. | [`models/node.py`](../backend/app/models/node.py) | “GPU server A” in an experiment should map to one `Node`, not a new GPU inventory. | Agreed vocabulary |
| **`Cluster`** | Persisted grouping of compute nodes with one `topology_type`; has a name, dimensions, and wrap settings in the current grid-oriented schema. | [`models/cluster.py`](../backend/app/models/cluster.py) | Different clusters can be torus or mesh. A **single cluster** should select exactly one cluster-level topology. | Live identity; graph integration proposed |
| **`Node`** | Persisted physical compute server belonging to exactly one cluster; owns its allocatable `ResourceNode` units and exposes node status. | [`models/node.py`](../backend/app/models/node.py) | Node 41 can provide four GPU devices. It is not a switch or a GPU core. | Live |
| **`ResourceNode` / resource unit** | One individually tracked, allocatable unit belonging to exactly one node, with a type, per-type index, and resource status. Database table: `node_resource`. | [`models/resourceNode.py`](../backend/app/models/resourceNode.py) | GPU index 2 on Node 41 is one unit. `ResourceNode` is **not** another compute node. | Live |
| **`ResourceType`** | Type of requested/allocated unit: `CPU`, `GPU`, or `MEM`. | [`enums/resourceType.py`](../backend/app/enums/resourceType.py) | A requirement for `GPU: 2` asks for two units labeled GPU. | Live |
| **`resource_type_index`** | Index distinguishing resource units of the same type within one node; unique together with node and resource type. | [`models/resourceNode.py`](../backend/app/models/resourceNode.py) | GPU indices 0 and 1 on one node designate separate records, not CUDA cores. | Live |
| **Free GPU count** | Number of GPU resource units on a node whose `ResourceStatus` is `AVAILABLE`. It is computed from the canonical unit records. | [`Node.free_resources()`](../backend/app/models/node.py) | Four installed GPUs with two allocated means two free GPU units. | Live |
| **`NodeStatus`** | Aggregate node state: `IDLE`, `ALLOCATED`, `MIXED`, or `DOWN`. | [`enums/nodeStatus.py`](../backend/app/enums/nodeStatus.py), [`domain/placer.py`](../backend/app/domain/placer.py) | `MIXED` means not all resource units share the same available/allocated state. It is not a network-link state. | Live |
| **`ResourceStatus`** | State of an individual unit: `AVAILABLE`, `ALLOCATED`, `UNAVAILABLE`, or `FAILED`. | [`enums/resourceStatus.py`](../backend/app/enums/resourceStatus.py) | A down node's released resources become `UNAVAILABLE`, rather than automatically placeable. | Live |
| **Memory unit granularity** | The meaning of one `MEM` resource unit (e.g., a fixed-size memory block) is not established by the enum alone. | [`ResourceType`](../backend/app/enums/resourceType.py), [`ResourceNode`](../backend/app/models/resourceNode.py) | Do **not** assume one `MEM` unit means one GiB unless explicitly specified. | Open |

## 2. Jobs, allocations, and policy boundaries

| Term | Canonical definition and ownership | Code reference | Example / important distinction | Status |
| --- | --- | --- | --- | --- |
| **`Institute`** | Persisted organization owning clients and institute-level quotas, reservations, and usage accounting. | [`models/institute.py`](../backend/app/models/institute.py) | Two clients of one institute share that institute's limits. | Live |
| **`Client`** | Persisted job-submitting owner associated with one institute. Not an HTTP/WebSocket connection. | [`models/client.py`](../backend/app/models/client.py) | A client submits jobs through REST, but the ORM record is not a live socket. | Live |
| **`Job`** | Submitted work request with client, requirements, priority, estimated duration, and lifecycle status; does not persist an assigned cluster. | [`models/job.py`](../backend/app/models/job.py), [`domain/server.py`](../backend/app/domain/server.py) | A job asks for four GPUs; its eventual allocation records where they were obtained. `Job.duration` is a hint, not measured runtime. | Live |
| **`ResourceRequirement`** | A job's requested resource type and amount; request, not fulfillment. | [`models/resourceRequirement.py`](../backend/app/models/resourceRequirement.py) | `GPU: 4` remains the request even if the four units span two nodes. | Live |
| **`JobStatus`** | Lifecycle state: `PENDING`, `QUEUED`, `RUNNING`, `COMPLETED`, `CANCELLED`, `FAILED`. | [`enums/jobStatus.py`](../backend/app/enums/jobStatus.py) | `QUEUED` is not an allocation guarantee or a start-time commitment. | Live |
| **`Priority`** | Job priority level: `LOW`, `NORMAL`, `HIGH`, or `URGENT`. | [`enums/priority.py`](../backend/app/enums/priority.py) | Priority affects queue ordering when `PrioritySort` is configured, not GPU topology. | Live |
| **`PendingJob`** | Lightweight queued reference containing job ID and priority, not a retained ORM `Job` instance. | [`domain/scheduler.py`](../backend/app/domain/scheduler.py) | The server reloads a job in the current DB session before placement. | Live |
| **`JobEvent`** | Persisted event log entry recording a job status/event and its time and comment; not the sole source of current state. | [`models/jobEvent.py`](../backend/app/models/jobEvent.py) | An allocation attempt may add an event while `Job.status` remains the current state. | Live |
| **`Allocation`** | Persisted record of fulfillment and its execution interval/status for a job. | [`models/allocation.py`](../backend/app/models/allocation.py) | Allocation begins when units are assigned, and ends when resources are released. | Live |
| **`AllocationNode`** | Association between an allocation and one specific `ResourceNode`; despite its name, it identifies a **resource unit**, not an entire compute node. | [`models/allocationNode.py`](../backend/app/models/allocationNode.py) | Four allocated GPUs correspond to four unit associations. | Live |
| **`AllocationStatus`** | Allocation lifecycle enum: `PENDING`, `ALLOCATED`, `ACTIVE`, `RELEASED`, `FAILED`. | [`enums/AllocationStatus.py`](../backend/app/enums/AllocationStatus.py) | This is distinct from `JobStatus` and `ResourceStatus`. | Live |
| **`Quota`** | Institute-level limit on concurrently running resource units, configured by calendar month and checked at job admission; it is not a cumulative GPU-hour budget. | [`models/quota.py`](../backend/app/models/quota.py), [`domain/server.py`](../backend/app/domain/server.py) | Requesting more concurrent GPUs than an institute's current monthly limit is rejected before queueing. | Live |
| **`Reservation`** | Time-bounded reservation of specified nodes for an institute. | [`models/reservation.py`](../backend/app/models/reservation.py) | Reserved nodes can be excluded from another institute's placement candidates. | Live |
| **`NodeReservation`** | Join record associating a reserved node with a reservation. | [`models/nodeReservation.py`](../backend/app/models/nodeReservation.py) | One reservation may cover several nodes. | Live |
| **`ResourceUsage`** | Institute-level schema for recorded resource consumption; the current application does not populate this table. | [`models/resourceUsage.py`](../backend/app/models/resourceUsage.py), [`decisions.md`](decisions.md) | GPU-hours would be usage, not currently free GPUs or a live quota. | Schema only; not populated |

## 3. Scheduler, placer, and deterministic choices

| Term | Canonical definition and ownership | Code reference | Example / important distinction | Status |
| --- | --- | --- | --- | --- |
| **`Scheduler`** | Per-cluster queue manager deciding **which job to attempt next**; delegates resource selection. | [`domain/scheduler.py`](../backend/app/domain/scheduler.py) | Scheduler answers *when to attempt*, not *which GPU*. | Live |
| **`SortStrategy`** | Policy governing queued-job order. | [`domain/sort_strategy.py`](../backend/app/domain/sort_strategy.py) | Replace FIFO with priority order without changing spatial placement. | Live |
| **`FifoSort`** | First-enqueued, first-considered queue policy. | [`domain/sort_strategy.py`](../backend/app/domain/sort_strategy.py) | Earlier enqueued jobs receive earlier attempts, subject to server drain behavior. | Live |
| **`PrioritySort`** | Queue policy ordering urgent before high, normal, and low; preserves FIFO within equal priority. | [`domain/sort_strategy.py`](../backend/app/domain/sort_strategy.py) | Two `URGENT` jobs retain insertion order. | Live |
| **`Placer`** | Transaction-local component deciding **where** and on which precise resource units to fulfill a job. Operates on ORM objects supplied by `Server`, without its own DB query/commit. | [`domain/placer.py`](../backend/app/domain/placer.py) | Filters available nodes, asks a policy to rank/select, marks chosen units allocated. | Live |
| **`PlaceAlgorithm`** | Swappable policy for selecting or ranking candidate nodes using a topology view. | [`domain/place_algorithm.py`](../backend/app/domain/place_algorithm.py) | Pack and Spread consume the same view interface today. | Live |
| **`PackAlgorithm`** | Prefers candidates with minimum grid distance to any already occupied node; falls back to lowest node ID when none is occupied. | [`domain/place_algorithm.py`](../backend/app/domain/place_algorithm.py) | A candidate next to an allocated node ranks ahead of a distant candidate. | Live; grid-based |
| **`SpreadAlgorithm`** | Prefers candidates with maximum grid distance from the nearest occupied node; same empty-cluster fallback. | [`domain/place_algorithm.py`](../backend/app/domain/place_algorithm.py) | A distant node ranks ahead of a nearby node. | Live; grid-based |
| **Candidate** | Node that remains eligible after applicable resource and policy constraints; it is not necessarily selected. | [`Placer.filter_nodes()`](../backend/app/domain/placer.py) | Three nodes may have sufficient free GPU units, but only one gets chosen first. | Live |
| **Resource feasibility** | Whether enough qualifying resource units are available to meet a job's requirements, potentially across nodes. | [`Placer.has_enough_capacity()`](../backend/app/domain/placer.py) | Four free GPUs across two nodes may satisfy raw capacity even if neither node has four alone. | Live |
| **`rank()` versus `select()`** | `rank()` returns a deterministic preference order; `select()` chooses its first node. | [`domain/place_algorithm.py`](../backend/app/domain/place_algorithm.py) | Equal scores are broken by node ID in current Pack/Spread. | Live |
| **Single-node versus multi-node placement** | A job is placed wholly on one node when possible; otherwise the placer can distribute requested units over multiple nodes. | [`Placer.place()`](../backend/app/domain/placer.py) | A four-GPU request can become 2+2 across two nodes. Network communication cost is not optimized today. | Live; network-aware extension proposed |
| **Admission** | Early decision whether a submitted job is allowable under client, quota, and total-capacity rules. | [`domain/server.py`](../backend/app/domain/server.py) | Quota rejection happens before placement; temporary lack of free GPUs may instead leave a job queued. | Live |
| **Allocation / release** | Transition of specific `ResourceNode` statuses into and out of `ALLOCATED`, with node aggregate state recomputed. | [`domain/placer.py`](../backend/app/domain/placer.py) | Releasing from a `DOWN` node does not make those units available. | Live |
| **Transaction-local / row lock** | The placer uses the request transaction's ORM objects while `Server` obtains row locks protecting contended allocation state. | [`Server._build_placer()`](../backend/app/domain/server.py) | Two concurrent attempts must not allocate the same GPU unit. | Live |
| **Network-aware placement** | Proposed extension in which topology connectivity and communication constraints affect actual resource selection. | [#87](https://github.com/labo-man002/job-scheduler/issues/87) | Choosing GPUs under one leaf may reduce communication cost, but is not today's Pack/Spread behavior. | Proposed |

## 4. Cluster topology and distance vocabulary

| Term | Canonical definition and ownership | Code reference | Example / important distinction | Status |
| --- | --- | --- | --- | --- |
| **Cluster-level topology** | The selected representation of connectivity among a cluster's compute nodes. Exactly one type is selected per cluster. | [`Cluster.topology_type`](../backend/app/models/cluster.py) | A cluster is configured as a torus **or** leaf-spine, not both at the same cluster-network layer. | Live selector; leaf-spine option proposed |
| **`TopologyType`** | Enum identifying supported/requested topology family. Currently `RING`, `MESH_2D`, `TORUS_2D`, `TORUS_3D`, and `FAT_TREE`. | [`enums/topologyType.py`](../backend/app/enums/topologyType.py) | `LEAF_SPINE` is **not** an existing enum member. | Live |
| **`Topology`** | Current domain object that accepts a cluster and builds a grid-oriented view over nodes. | [`domain/topology.py`](../backend/app/domain/topology.py) | `Topology(cluster).build_view(nodes)` constructs a placement snapshot. | Live |
| **`TopologyView`** | Disposable view of nodes and coordinate-grid operations used by placement algorithms. | [`domain/topology.py`](../backend/app/domain/topology.py) | `distance(a,b)` computes grid distance, not network-path latency. | Live |
| **Grid / coordinate topology** | Connectivity inferred from integer coordinates along dimensions, optionally wrapping at edges. | [`domain/topology.py`](../backend/app/domain/topology.py) | Nodes at `(0,0)` and `(1,0)` are adjacent in a 2D grid. | Live |
| **`RING`** | One-dimensional grid topology type. Actual boundary connection follows the cluster's `wrap` flag; creation currently does not force `wrap=True` for this enum. | [`enums/topologyType.py`](../backend/app/enums/topologyType.py), [`domain/topology.py`](../backend/app/domain/topology.py) | With `wrap=True`, the first and last nodes are neighbors; with `wrap=False`, the coordinate math behaves like a line. | Live; naming/validation nuance |
| **`MESH_2D`** | Two-dimensional grid without wraparound. | [`domain/server.py`](../backend/app/domain/server.py) | Edge nodes have fewer grid neighbors. | Live |
| **`TORUS_2D` / `TORUS_3D`** | Two-/three-dimensional grid whose wrapped axes connect opposite boundaries when wrap is enabled. | [`domain/topology.py`](../backend/app/domain/topology.py) | In a wrapped dimension of size 8, coordinate 0 is one step from 7. | Live |
| **`FAT_TREE`** | Enum value reserved for a network family, but **not supported** in current cluster creation or grid distance. | [`domain/server.py`](../backend/app/domain/server.py), [`domain/topology.py`](../backend/app/domain/topology.py) | It must not be treated as working leaf-spine support. | Declared, unsupported |
| **Leaf-spine cluster topology** | Proposed alternative cluster-level network graph with compute-node NICs attached to leaf switches and leaves connected to spines. | [#87](https://github.com/labo-man002/job-scheduler/issues/87), [#93](https://github.com/labo-man002/job-scheduler/issues/93) | A node under leaf A reaches a node under leaf B through a spine. | Proposed integration |
| **Coordinates / dimension** | Node coordinates and cluster axis sizes for current grid geometry. | [`models/node.py`](../backend/app/models/node.py), [`models/cluster.py`](../backend/app/models/cluster.py) | `dimension=[4,4]` supplies 2D grid bounds. These values do not identify physical leaf/spine switches. | Live grid fields |
| **Wrap / wraparound** | Whether an axis's boundaries connect through modular coordinate arithmetic. | [`domain/topology.py`](../backend/app/domain/topology.py) | A torus may wrap; a mesh must not. | Live |
| **Neighbor** | Node adjacent by one coordinate step in the active grid view, with wrapping when configured. | [`TopologyView.neighbors()`](../backend/app/domain/topology.py) | This is not automatically the same as direct physical-cable adjacency. | Live grid concept |
| **Grid distance** | Sum of per-axis absolute coordinate differences, taking shortest wrapped difference when enabled. | [`TopologyView.distance()`](../backend/app/domain/topology.py) | Distance `2` is a grid metric, **not** 2 microseconds of latency. | Live |
| **Network path / route** | Sequence of operational links between graph endpoints; distinct from an abstract grid distance. | [`leaf_spine/topology.py`](../backend/app/domain/leaf_spine/topology.py) | Server A → leaf A → spine → leaf B → server B describes a physical network route. | Prototype |

## 5. Leaf-spine network domain

The following types are in [`domain/leaf_spine/`](../backend/app/domain/leaf_spine/), the in-memory prototype merged in [#86](https://github.com/labo-man002/job-scheduler/pull/86). They are **not yet part of `Server._build_placer()`**. See [`gpu-leaf-spine.md`](gpu-leaf-spine.md) for detailed API semantics.

| Term | Canonical definition and ownership | Code reference | Example / important distinction | Status |
| --- | --- | --- | --- | --- |
| **`LeafSpineTopology` / fabric** | Network graph owning switch/server-attachment registries, physical link definitions, and derived adjacency indexes. | [`leaf_spine/topology.py`](../backend/app/domain/leaf_spine/topology.py) | The fabric can find a path without allocating any GPU. | Prototype |
| **Leaf switch** | Switch to which compute servers attach; links upward to spine switches. | [`SwitchRole.LEAF`](../backend/app/domain/leaf_spine/types.py) | Node 41's NIC connects to a leaf port. | Prototype |
| **Spine switch** | Switch interconnecting leaf switches in the two-tier fabric; does not directly host GPU resource units. | [`SwitchRole.SPINE`](../backend/app/domain/leaf_spine/types.py) | Cross-leaf traffic usually traverses a spine. | Prototype |
| **`Switch`** | Immutable device snapshot with identity, leaf/spine role, hardware configuration, operational state, and generated ports. | [`leaf_spine/devices.py`](../backend/app/domain/leaf_spine/devices.py) | `leaf-a` may have four physical ports. | Prototype |
| **`SwitchHardwareConfig` / `PortGroupConfig`** | Immutable description of a switch's port counts and speeds, shared by leaf or spine devices. | [`leaf_spine/hardware.py`](../backend/app/domain/leaf_spine/hardware.py) | A group of four 400-Gbps ports defines physical port capacity. | Prototype |
| **`Port`** | Numbered switch endpoint with capacity and operational state. | [`leaf_spine/devices.py`](../backend/app/domain/leaf_spine/devices.py) | `leaf-a.p1` may be occupied by a cable to `spine-1.p2`. | Prototype |
| **`NetworkInterface` / NIC** | Endpoint on a compute host through which that host connects to the network. Prototype `GpuServer` exposes one `nic0`. | [`leaf_spine/devices.py`](../backend/app/domain/leaf_spine/devices.py) | The NIC belongs conceptually to Node 41; it does not own the node's GPUs. | Prototype; ownership model open |
| **`GpuServer`** | Immutable network-facing identity with its own ID, mapped `Node.node_id`, one NIC capacity and network-operational state. It does **not** track free GPU units. | [`leaf_spine/devices.py`](../backend/app/domain/leaf_spine/devices.py) | `GpuServer("gpu-a", node_id=41, ...)` refers to the existing physical Node 41. Retain wrapper or reference Node directly: **open**. | Prototype / Open |
| **`NetworkEndpoint`** | Abstract contract for a physical link termination, implemented by ports and NICs in the prototype. | [`leaf_spine/devices.py`](../backend/app/domain/leaf_spine/devices.py) | A cable connects endpoints, not two GPU capacity counters. | Prototype |
| **`DeviceRef` / `EndpointRef`** | Immutable identifiers for a device and its specific link endpoint. | [`leaf_spine/types.py`](../backend/app/domain/leaf_spine/types.py) | `(SWITCH, leaf-a, p1)` identifies an exact physical port. | Prototype |
| **`Link`** | Immutable, undirected physical connection between two endpoint references, with kind, capacity, latency, and operational state. | [`leaf_spine/link.py`](../backend/app/domain/leaf_spine/link.py) | A leaf–spine cable and a server–leaf cable are different link kinds. | Prototype |
| **`LinkKind`** | Currently `LEAF_SPINE` or `SERVER_LEAF`; other endpoint pairings are rejected. | [`leaf_spine/types.py`](../backend/app/domain/leaf_spine/types.py) | A server directly linked to a spine is invalid in the current two-tier model. | Prototype |
| **Physical connectivity** | Cable/link registration independent of whether a device or link is currently operational. | [`LeafSpineTopology`](../backend/app/domain/leaf_spine/topology.py) | Setting a link down does not free its physical ports for a second cable. | Prototype |
| **Operational reachability** | Existence of a usable route excluding down links, switches, ports, servers, and NICs. | [`LeafSpineTopology.find_path()`](../backend/app/domain/leaf_spine/topology.py) | An attached server can be physically connected but temporarily unreachable. | Prototype |
| **`NetworkPath`** | Immutable result describing a selected path and its link sequence, cumulative latency, and other path properties. | [`leaf_spine/link.py`](../backend/app/domain/leaf_spine/link.py) | A result with 2 links is a path snapshot, not a bandwidth reservation. | Prototype |
| **`find_path()`** | Operational bidirectional path search minimizing cumulative latency; ties prefer fewer hops and then lexical link-ID sequence. Uses nominal link constraints. | [`leaf_spine/topology.py`](../backend/app/domain/leaf_spine/topology.py) | Equal-latency routes select one deterministically. | Prototype |
| **`GpuCandidateFinder`** | Read-only query combining existing ORM-node free GPU units with fabric reachability from a specified root switch. | [`leaf_spine/gpu_candidates.py`](../backend/app/domain/leaf_spine/gpu_candidates.py) | Returns reachable nodes with at least two free GPUs; it does **not** place a job. | Prototype |
| **`GpuCandidate`** | Query result containing network server ID, mapped compute node ID, free GPU-unit IDs, and a path. | [`leaf_spine/gpu_candidates.py`](../backend/app/domain/leaf_spine/gpu_candidates.py) | It is an observation, not a persisted allocation. | Prototype |
| **Root switch** | Starting switch for the prototype's candidate/path query, chosen by the caller. Not a universal scheduler root. | [`GpuCandidateFinder.find_candidates()`](../backend/app/domain/leaf_spine/gpu_candidates.py) | `"spine-1"` is the start of a candidate search. | Prototype |
| **Link capacity / nominal bandwidth** | Configured physical speed of a link, in Gbps; prototype path filtering checks this number, not live remaining bandwidth. | [`leaf_spine/link.py`](../backend/app/domain/leaf_spine/link.py) | A nominal 100-Gbps link can be congested; the prototype does not model contention. | Prototype |
| **Latency** | Per-link configured traversal cost, in microseconds, summed along a path. | [`leaf_spine/link.py`](../backend/app/domain/leaf_spine/link.py) | 2 µs + 1 µs = 3 µs modeled path latency. It is not observed wall-clock GPU-job runtime. | Prototype |
| **Residual/available bandwidth** | Bandwidth left after accounting for competing traffic or reservations. **Not tracked** by the v1 fabric. | [#93](https://github.com/labo-man002/job-scheduler/issues/93) | `min_link_capacity_gbps=100` does not guarantee 100 Gbps is free. | Proposed |
| **Network reservation** | Proposed mechanism for atomically claiming path/bandwidth capacity across placements. Distinct from institute-level `Reservation` of compute nodes. | [#87](https://github.com/labo-man002/job-scheduler/issues/87) | Placing a job does not currently reserve network links. | Proposed |

## 6. Related HPC terms — conceptual, not automatically implemented

| Term | Meaning and example | System status |
| --- | --- | --- |
| **GPU device versus GPU core** | One GPU device contains many execution units; the scheduler currently counts GPU **devices** as resource units, not CUDA/streaming cores. | Concept; device-level accounting live |
| **CPU core versus CPU socket** | A core is one processing unit within a processor package/socket. Code counts `CPU` resource units but does not model a detailed socket topology. | Concept |
| **NUMA** | Non-uniform memory access: latency/bandwidth to memory may depend on the requesting processor or locality domain. | Concept, not modeled |
| **PCIe** | Common local high-speed peripheral interconnect, e.g., CPU↔NIC or CPU↔GPU. | Concept, not modeled |
| **NVLink / NVSwitch** | NVIDIA technologies for high-bandwidth intra-server GPU communication; not the same as the external leaf-spine Ethernet/InfiniBand-style fabric. | Concept, not modeled |
| **Intra-node / inter-node communication** | Traffic within one compute host versus traffic between different hosts. | Concept; relevant to proposed placement cost |
| **RDMA** | Remote direct memory access: network data movement with reduced CPU participation in appropriate hardware/software stacks. | Concept, not modeled |
| **ECMP** | Equal-cost multipath forwarding; a real fabric may spread flows across several equivalent routes. Prototype selects one deterministic graph path, not real ECMP flow routing. | Concept, not modeled |
| **Dragonfly** | A different high-performance network topology with router groups and global connectivity; not an implemented `TopologyType`. | Concept, not modeled |

## 7. Non-negotiable distinctions and examples

1. **One cluster-level topology:** `Cluster.topology_type` chooses one connectivity family for that cluster. Independent clusters may choose different families. Intra-node GPU fabrics (e.g., hypothetical NVLink) are a different physical layer, not a second cluster-level topology.
2. **One compute identity:** `Node` is the canonical physical host and `ResourceNode` is the canonical unit. A leaf-spine attachment may refer to a node, but must never create a competing GPU inventory.
3. **Scheduling is not placement:** `Scheduler` chooses the next *attempt*; `Placer` chooses specific resource units; `Server` handles admission, transaction context, and persistence.
4. **Candidates are not allocations:** a `GpuCandidateFinder` result is read-only even if it knows GPU IDs and a network path.
5. **Grid distance is not network cost:** grid Manhattan-like distance, hop count, latency, and bandwidth represent different quantities with different units.
6. **Physical links are not available bandwidth:** a registered link remains wired while down; nominal speed is not residual capacity.
7. **Resource reservation is not network reservation:** an institute's reserved compute nodes do not imply bandwidth claims along links.

### Two placements of the same resource request

Suppose a four-GPU job could fit either on Node 41 (four free GPUs) or across Nodes 42 and 43 (two each). Both satisfy **resource feasibility**. A communication-heavy workload might prefer Node 41 for locality, whereas independent workers might tolerate distribution. The current placer prefers single-node fit when possible, then may distribute units; it does **not** model a communication objective or network-bandwidth reservation. Any proposed network-aware policy must specify its cost function and what happens when links are disconnected or constrained.

## 8. Open vocabulary/design decisions

Do not resolve these merely by changing glossary wording. Record the eventual decisions in [`decisions.md`](decisions.md) and update this glossary afterward.

| Decision | What must be established | Tracking |
| --- | --- | --- |
| **`GpuServer` identity** | Keep a thin node/NIC attachment wrapper or use `Node` IDs as endpoint identity directly; define network-state ownership and cluster-membership validation. | [#87](https://github.com/labo-man002/job-scheduler/issues/87), [#93](https://github.com/labo-man002/job-scheduler/issues/93) |
| **Graph topology configuration** | How `LEAF_SPINE` is represented in the type enum and schema, and how graph clusters avoid irrelevant mandatory grid `coordinates`, `dimension`, and `wrap` fields. | [#87](https://github.com/labo-man002/job-scheduler/issues/87), [#93](https://github.com/labo-man002/job-scheduler/issues/93) |
| **`MEM` resource granularity** | Size/unit and relation to actual memory capacity; avoid calling one unspecified unit “1 GiB.” | Follow-up modeling decision |
| **Network-aware placement contract** | Constraints, cost function, candidate combination, failure behavior, ties, and the boundary between immutable path queries and stateful reservations. | [#87](https://github.com/labo-man002/job-scheduler/issues/87), [#93](https://github.com/labo-man002/job-scheduler/issues/93) |
| **Advanced hardware scope** | Whether to model GPUs by device/model, sockets/NUMA domains, multi-NIC hosts, NVLink, NVSwitch, or real flow routing; none should be implied by today's prototype. | [#85](https://github.com/labo-man002/job-scheduler/issues/85), future issues |

## Further reading and maintenance

- [Architecture and current execution sequence](architecture.md)
- [Previously documented modeling decisions](decisions.md)
- [Leaf-spine v1 prototype, examples, and explicit limitations](gpu-leaf-spine.md)
- [#94 — Canonical glossary](https://github.com/labo-man002/job-scheduler/issues/94)
- [#93 — Leaf-spine semantics and deterministic behavior](https://github.com/labo-man002/job-scheduler/issues/93)
- [#87 — Network-aware placement integration](https://github.com/labo-man002/job-scheduler/issues/87)

For each future domain change: update the corresponding code/tests and decision record, then update any affected glossary entry in the same PR. Use new terms only after defining their meaning and ownership. This glossary is documentation, **not** a replacement for executable validation or tests.
