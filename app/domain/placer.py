from app.enums.nodeStatus import NodeStatus
from app.enums.resourceStatus import ResourceStatus
from app.models.job import Job
from app.models.node import Node
from app.models.resourceNode import ResourceNode

from .place_algorithm import PlaceAlgorithm
from .topology import Topology


class Placer:
    """One Placer per Cluster. Operates directly on the real ORM Node/ResourceNode
    objects passed in — never queries the DB or commits itself. Whoever loads `nodes`
    and calls place()/release_resource() (Server, out of scope for this ticket) is
    responsible for the session and for committing afterward."""

    def __init__(self, nodes: list[Node], algorithm: PlaceAlgorithm, topology: Topology):
        self.nodes = nodes
        self.algorithm = algorithm
        self.topology = topology

    def set_algorithm(self, algorithm: PlaceAlgorithm) -> None:
        self.algorithm = algorithm

    def filter_nodes(self, nodes: list[Node], job: Job) -> list[Node]:
        return [
            node
            for node in nodes
            if all(
                len(node.free_resources(req.resource_type)) >= req.amount
                for req in job.requirements
            )
        ]

    def place(self, job: Job) -> list[ResourceNode] | None:
        view = self.topology.build_view(self.nodes)

        single_node_candidates = self.filter_nodes(self.nodes, job)
        if single_node_candidates:
            chosen = self.algorithm.select(single_node_candidates, job, view)
            needed = {req.resource_type: req.amount for req in job.requirements}
            return self._reserve_from(chosen, needed)

        if not self.has_enough_capacity(job):
            return None

        remaining = {req.resource_type: req.amount for req in job.requirements}
        reserved = []
        for node in self.algorithm.rank(self.nodes, job, view):
            if all(amount <= 0 for amount in remaining.values()):
                break
            taken = self._reserve_from(node, remaining)
            reserved.extend(taken)
            for resource in taken:
                remaining[resource.resource_type] -= 1
        return reserved

    def has_enough_capacity(self, job: Job, nodes: list[Node] | None = None) -> bool:
        """Read-only capacity check -- lcaller ask "would this job ever fit here" against a different node
        set than self.nodes without risking an actual placement."""
        candidates = self.nodes if nodes is None else nodes
        for req in job.requirements:
            total_free = sum(len(node.free_resources(req.resource_type)) for node in candidates)
            if total_free < req.amount:
                return False
        return True

    def release_resource(self, resource_nodes: list[ResourceNode]) -> None:
        """A resource on a node marked DOWN releases to UNAVAILABLE, not
        AVAILABLE -- decommissioning waits for a running job to finish
        rather than evicting it (see docs/decisions.md), but once it does
        finish, the resource shouldn't quietly become placeable again."""
        affected_nodes = {resource.node for resource in resource_nodes}
        for resource in resource_nodes:
            resource.resource_status = (
                ResourceStatus.UNAVAILABLE if resource.node.status == NodeStatus.DOWN else ResourceStatus.AVAILABLE
            )
        for node in affected_nodes:
            self._recompute_status(node)

    def _reserve_from(self, node: Node, needed: dict) -> list[ResourceNode]:
        reserved = []
        for resource_type, amount in needed.items():
            if amount <= 0:
                continue
            for resource in node.free_resources(resource_type)[:amount]:
                resource.resource_status = ResourceStatus.ALLOCATED
                reserved.append(resource)
        if reserved:
            self._recompute_status(node)
        return reserved

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
