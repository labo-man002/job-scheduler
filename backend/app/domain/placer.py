from itertools import combinations

from app.enums.nodeStatus import NodeStatus
from app.enums.resourceStatus import ResourceStatus
from app.models.job import Job
from app.models.node import Node
from app.models.resourceNode import ResourceNode

from .place_algorithm import PlaceAlgorithm
from .topology import PlacementTopology


class Placer:
    """Topology-independent placement orchestrator for one cluster.

    Candidate selection is read-only. ResourceNode statuses are changed only
    after a complete feasible allocation group has been selected.
    """

    def __init__(self, nodes: list[Node], algorithm: PlaceAlgorithm, topology: PlacementTopology):
        self.nodes = nodes
        self.algorithm = algorithm
        self.topology = topology

    def set_algorithm(self, algorithm: PlaceAlgorithm) -> None:
        self.algorithm = algorithm

    def filter_nodes(self, nodes: list[Node], job: Job) -> list[Node]:
        """Nodes that can satisfy every resource requirement on their own."""
        return [
            node for node in nodes
            if node.status != NodeStatus.DOWN
            and all(len(node.free_resources(req.resource_type)) >= req.amount for req in job.requirements)
        ]

    def find_candidates(self, job: Job) -> list[Node]:
        """Generic candidate discovery used by placement for CPU, GPU, or mixed jobs."""
        required = {req.resource_type for req in job.requirements}
        return [
            node for node in self.nodes
            if node.status != NodeStatus.DOWN
            and any(node.free_resources(resource_type) for resource_type in required)
        ]

    def place(self, job: Job) -> list[ResourceNode] | None:
        if not job.requirements:
            return None
        min_nodes = getattr(job, "min_nodes", 1) or 1
        max_nodes = getattr(job, "max_nodes", None)
        if type(min_nodes) is not int or min_nodes < 1:
            raise ValueError("min_nodes must be a positive integer")
        if max_nodes is not None and (type(max_nodes) is not int or max_nodes < min_nodes):
            raise ValueError("max_nodes must be greater than or equal to min_nodes")

        view = self.topology.build_view(self.nodes)
        candidates = self.find_candidates(job)
        if not candidates or not self.has_enough_capacity(job, candidates):
            return None

        ranked = self.algorithm.rank(candidates, job, view)
        rank_index = {node.node_id: index for index, node in enumerate(ranked)}
        upper = min(max_nodes or len(ranked), len(ranked))
        selected_group = None

        # Exact deterministic search: smallest group first, then pairwise
        # locality, then Pack/Spread preference, then stable Node IDs.
        for size in range(min_nodes, upper + 1):
            feasible = []
            for group in combinations(ranked, size):
                if not self._has_capacity(job, group):
                    continue
                if not self._satisfies_network_constraints(job, group, view):
                    continue
                locality = sum(view.distance(a, b) for a, b in combinations(group, 2))
                policy_tie = sum(rank_index[node.node_id] for node in group)
                ids = tuple(sorted(node.node_id for node in group))
                feasible.append(((locality, policy_tie, ids), group))
            if feasible:
                selected_group = min(feasible, key=lambda item: item[0])[1]
                break

        if selected_group is None:
            return None

        # Build the complete reservation plan before mutating any ORM object.
        remaining = {req.resource_type: req.amount for req in job.requirements}
        plan: list[tuple[Node, list[ResourceNode]]] = []
        for node in sorted(selected_group, key=lambda n: n.node_id):
            taken = []
            for resource_type, amount in remaining.items():
                if amount <= 0:
                    continue
                units = node.free_resources(resource_type)[:amount]
                taken.extend(units)
                remaining[resource_type] -= len(units)
            if taken:
                plan.append((node, taken))
        if any(amount > 0 for amount in remaining.values()):
            return None  # defensive: inventory changed between planning and reservation

        reserved = []
        for node, resources in plan:
            for resource in resources:
                resource.resource_status = ResourceStatus.ALLOCATED
                reserved.append(resource)
            self._recompute_status(node)
        return reserved

    def _has_capacity(self, job: Job, group: tuple[Node, ...] | list[Node]) -> bool:
        for req in job.requirements:
            if sum(len(node.free_resources(req.resource_type)) for node in group) < req.amount:
                return False
        return True

    def _satisfies_network_constraints(self, job: Job, group: tuple[Node, ...], view) -> bool:
        # Jobs without explicit network requirements remain topology-agnostic.
        min_bandwidth = getattr(job, "min_bandwidth_gbps", None)
        max_latency = getattr(job, "max_latency_us", None)
        require_full_connectivity = getattr(job, "require_full_connectivity", False)
        if not (require_full_connectivity or min_bandwidth is not None or max_latency is not None):
            return True
        for a, b in combinations(group, 2):
            if not view.is_reachable(a, b):
                return False
            metrics = view.path_metrics(
                a, b, min_bandwidth_gbps=min_bandwidth, max_latency_us=max_latency
            )
            if metrics is None:
                return False
        return True

    def has_enough_capacity(self, job: Job, nodes: list[Node] | None = None) -> bool:
        """Read-only cluster-wide capacity check."""
        candidates = self.nodes if nodes is None else nodes
        return self._has_capacity(job, candidates)

    def release_resource(self, resource_nodes: list[ResourceNode]) -> None:
        affected_nodes = {resource.node for resource in resource_nodes}
        for resource in resource_nodes:
            resource.resource_status = (
                ResourceStatus.UNAVAILABLE if resource.node.status == NodeStatus.DOWN else ResourceStatus.AVAILABLE
            )
        for node in affected_nodes:
            self._recompute_status(node)

    def _recompute_status(self, node: Node) -> None:
        if node.status == NodeStatus.DOWN:
            return
        statuses = {r.resource_status for r in node.resources}
        if not statuses or statuses == {ResourceStatus.AVAILABLE}:
            node.status = NodeStatus.IDLE
        elif statuses == {ResourceStatus.ALLOCATED}:
            node.status = NodeStatus.ALLOCATED
        else:
            node.status = NodeStatus.MIXED
