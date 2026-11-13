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
        self.available_node_ids: set[int] | None = None

    def set_algorithm(self, algorithm: PlaceAlgorithm) -> None:
        self.algorithm = algorithm

    def filter_nodes(self, nodes: list[Node], job: Job) -> list[Node]:
        """Nodes that can satisfy every resource requirement on their own."""
        return [
            node for node in nodes
            if node.status != NodeStatus.DOWN
            and all(len(node.free_resources(req.resource_type)) >= req.amount for req in job.requirements)
        ]

    def find_candidates(self, job: Job, nodes: list[Node] | None = None) -> list[Node]:
        """Generic candidate discovery used by placement for CPU, GPU, or mixed jobs."""
        required = {req.resource_type for req in job.requirements}
        inventory = self.nodes if nodes is None else nodes
        return [
            node for node in inventory
            if node.status != NodeStatus.DOWN
            and any(node.free_resources(resource_type) for resource_type in required)
        ]

    def place(self, job: Job) -> list[ResourceNode] | None:
        if not job.requirements:
            return None
        view = self.topology.build_view(self.nodes)
        eligible_nodes = [
            node for node in self.nodes
            if self.available_node_ids is None or node.node_id in self.available_node_ids
        ]
        candidates = self.find_candidates(job, eligible_nodes)
        selected_group = self._select_group(job, candidates, view)
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

    def can_place(self, job: Job) -> bool:
        """Read-only feasibility check using the current per-job eligibility set."""
        if not job.requirements:
            return False
        view = self.topology.build_view(self.nodes)
        eligible_nodes = [
            node for node in self.nodes
            if self.available_node_ids is None or node.node_id in self.available_node_ids
        ]
        candidates = self.find_candidates(job, eligible_nodes)
        return self._select_group(job, candidates, view) is not None

    def _select_group(self, job: Job, candidates: list[Node], view) -> tuple[Node, ...] | None:
        if not candidates or not self.has_enough_capacity(job, candidates):
            return None

        ranked = self.algorithm.rank(candidates, job, view)
        rank_index = {node.node_id: index for index, node in enumerate(ranked)}
        # Every multi-node allocation must be pairwise reachable. Network
        # locality is therefore an intrinsic placement objective, not a Job option.
        feasible = []
        for size in range(1, len(ranked) + 1):
            for group in self._iter_capacity_feasible_groups(ranked, size, job):
                if not self._is_group_reachable(group, view):
                    continue
                locality = self._group_locality(group, view)
                policy_tie = sum(rank_index[node.node_id] for node in group)
                ids = tuple(sorted(node.node_id for node in group))
                score = (locality, size, policy_tie, ids)
                feasible.append((score, group))

        return min(feasible, key=lambda item: item[0])[1] if feasible else None

    def _iter_capacity_feasible_groups(self, ranked: list[Node], size: int, job: Job):
        """Yield exact-size groups; prune only branches that cannot meet resource totals."""
        requirements = {req.resource_type: req.amount for req in job.requirements}
        capacities = [
            {resource_type: len(node.free_resources(resource_type)) for resource_type in requirements}
            for node in ranked
        ]

        def enough_capacity(start: int, slots: int, current: dict) -> bool:
            for resource_type, amount in requirements.items():
                best_remaining = sorted(
                    (capacity[resource_type] for capacity in capacities[start:]),
                    reverse=True,
                )[:slots]
                if current[resource_type] + sum(best_remaining) < amount:
                    return False
            return True

        def walk(start: int, slots: int, chosen: list[Node], current: dict):
            if slots == 0:
                yield tuple(chosen)
                return
            if len(ranked) - start < slots or not enough_capacity(start, slots, current):
                return
            last_start = len(ranked) - slots
            for index in range(start, last_start + 1):
                updated = {
                    resource_type: current[resource_type] + capacities[index][resource_type]
                    for resource_type in requirements
                }
                if not enough_capacity(index + 1, slots - 1, updated):
                    continue
                chosen.append(ranked[index])
                yield from walk(index + 1, slots - 1, chosen, updated)
                chosen.pop()

        initial = {resource_type: 0 for resource_type in requirements}
        yield from walk(0, size, [], initial)

    def _has_capacity(self, job: Job, group: tuple[Node, ...] | list[Node]) -> bool:
        for req in job.requirements:
            if sum(len(node.free_resources(req.resource_type)) for node in group) < req.amount:
                return False
        return True

    def _group_locality(self, group: tuple[Node, ...], view) -> float:
        """Sum of pairwise topology distances for the selected Node group."""
        return sum(view.distance(a, b) for a, b in combinations(group, 2))

    def _is_group_reachable(self, group: tuple[Node, ...], view) -> bool:
        """Require every selected Node pair to have an operational path."""
        return all(view.is_reachable(a, b) for a, b in combinations(group, 2))

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
