# Cluster Snapshot v0

## Purpose
`ClusterSnapshot` is the first stable contract between backend semantics and frontend rendering.
It should be useful in three modes:
- mock fixture driven UI development
- replayable demo scenarios
- live Slurm-backed current-state rendering

The snapshot should expose normalized state plus first-order derived meaning.

## Design Rules
- do not mirror raw Slurm structures directly
- keep canonical entities explicit
- include derived summaries needed by the hero screen
- support both current state rendering and explanation-oriented drilldowns
- stay MVP-sized and easy to evolve

## Top-Level Shape

```ts
type ClusterSnapshot = {
  snapshotId: string
  collectedAt: string
  cluster: ClusterInfo

  partitions: Partition[]
  topologyGroups: TopologyGroup[]
  nodes: Node[]
  jobs: Job[]
  allocations: Allocation[]

  summary: ClusterSummary
  fragmentation: FragmentationSummary
  pendingAnalysis: PendingAnalysisSummary

  warnings?: WarningMessage[]
}
```

## ClusterInfo

```ts
type ClusterInfo = {
  id: string
  name: string
  scheduler: "slurm"
  source: {
    type: "slurmrestd" | "cli" | "mock"
    version?: string
  }
}
```

## Partition

```ts
type Partition = {
  id: string
  name: string
  state: "up" | "down" | "inactive" | "drain"
  isDefault?: boolean
  nodeIds: string[]
  summary: {
    totalNodes: number
    idleNodes: number
    allocatedNodes: number
    mixedNodes: number
    downNodes: number
    drainedNodes: number
  }
}
```

## TopologyGroup

```ts
type TopologyGroup = {
  id: string
  name: string
  kind: "cluster" | "row" | "rack" | "chassis" | "switch" | "gpu-island" | "custom"
  parentId?: string
  childIds?: string[]
  nodeIds: string[]
  summary: {
    totalNodes: number
    freeNodes: number
    allocatedNodes: number
    mixedNodes: number
  }
}
```

## Node

```ts
type Node = {
  id: string
  name: string
  partitionIds: string[]
  topologyGroupIds: string[]
  state: "idle" | "allocated" | "mixed" | "down" | "drain" | "draining" | "reserved" | "unknown"
  features?: string[]
  reasons?: string[]
  resources: {
    cpu: ResourceCapacity
    memory: ResourceCapacity
    gpus?: GpuCapacity[]
    localStorage?: ResourceCapacity
  }
  locality?: {
    numaDomains?: number
    gpuFabric?: "none" | "pcie" | "nvlink" | "nvswitch" | "mixed" | "unknown"
  }
  allocation?: {
    jobIds: string[]
    exclusive: boolean
  }
}
```

## Resource Types

```ts
type ResourceCapacity = {
  total: number
  allocated: number
  free: number
  unit: "count" | "cores" | "threads" | "bytes" | "gib"
}

type GpuCapacity = {
  kind: string
  total: number
  allocated: number
  free: number
  model?: string
  migProfiles?: string[]
}
```

## Job

```ts
type Job = {
  id: string
  name?: string
  user: string
  account?: string
  partition: string
  qos?: string
  state: "pending" | "running" | "completing" | "completed" | "failed" | "cancelled"
  priority?: number
  submitTime?: string
  startTime?: string
  request: JobRequest
  placement?: JobPlacement
  pending?: PendingExplanation
}
```

## Job Request / Placement

```ts
type JobRequest = {
  nodes?: { min?: number; max?: number; exact?: number }
  cpu?: { total?: number; perNode?: number; perTask?: number }
  memory?: { perNode?: number; total?: number; unit: "gib" }
  gpu?: { total?: number; perNode?: number; model?: string }
  constraints?: string[]
  exclusive?: boolean
}

type JobPlacement = {
  allocationId?: string
  nodeIds?: string[]
  topologyGroupIds?: string[]
}
```

## Allocation

```ts
type Allocation = {
  id: string
  jobId: string
  nodeIds: string[]
  resources: {
    cpu: number
    memoryGiB: number
    gpus?: number
  }
  locality: {
    spansPartitions: boolean
    spansTopologyGroups: boolean
    topologyGroupCount: number
  }
}
```

## Pending Explanation

```ts
type PendingExplanation = {
  schedulerReason?: string
  category: "capacity" | "fragmentation" | "topology" | "constraint" | "policy" | "reservation" | "unknown"
  shortMessage: string
  details?: string[]
  blockers?: {
    insufficientCpu?: boolean
    insufficientMemory?: boolean
    insufficientGpu?: boolean
    insufficientEligibleNodes?: boolean
    localityNotSatisfied?: boolean
    constraintMismatch?: boolean
    reservationConflict?: boolean
  }
  fitAnalysis?: {
    eligibleNodeCount: number
    immediatelyPlaceable: boolean
    largestNodeBlock?: number
    largestGpuBlock?: number
    localityPreservingNodeBlock?: number
    fragmentedFreeCpu?: number
    fragmentedFreeGpu?: number
  }
}
```

## Summary Surfaces

```ts
type ClusterSummary = {
  totals: {
    nodes: number
    cpus: number
    memoryGiB: number
    gpus?: number
  }
  usage: {
    allocatedNodes: number
    idleNodes: number
    mixedNodes: number
    downNodes: number
    cpuUtilizationPct: number
    memoryUtilizationPct: number
    gpuUtilizationPct?: number
  }
  queue: {
    pendingJobs: number
    runningJobs: number
  }
}

type FragmentationSummary = {
  score: number
  level: "low" | "moderate" | "high"
  strandedCapacity: {
    cpu: number
    memoryGiB: number
    gpus?: number
  }
  largestPlaceableShapes: {
    exclusiveNodes: number
    cpuOnlyJobs?: {
      maxNodes: number
      maxCpuPerNode: number
    }
    gpuJobs?: {
      maxNodes: number
      maxGpuPerNode: number
    }
  }
  locality: {
    largestSingleTopologyGroupFreeBlock: number
    freeNodesSpreadScore: number
  }
}

type PendingAnalysisSummary = {
  totalPending: number
  byCategory: {
    capacity: number
    fragmentation: number
    topology: number
    constraint: number
    policy: number
    reservation: number
    unknown: number
  }
  mostBlockedJobIds: string[]
}
```

## WarningMessage

```ts
type WarningMessage = {
  level: "info" | "warning" | "error"
  code: string
  message: string
}
```

## Immediate Implementation Use
Milestone 1 should use this contract to:
- create static fixture snapshots
- drive frontend hero-shell development without live Slurm dependency
- guide backend normalization work
- clarify what should be computed in the backend versus rendered in the frontend

## First Fixture Scenarios
The first fixture set should include:
1. healthy baseline cluster
2. fragmented CPU-heavy cluster
3. GPU-constrained cluster
4. pending-heavy queue with obvious explainability targets

These fixtures should become the common language between backend, frontend, and demo work.
