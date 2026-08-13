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

    def place(self, job: Job) -> Node | None:
        candidates = self.filter_nodes(self.nodes, job)
        if not candidates:
            return None

        view = self.topology.build_view(self.nodes)
        chosen = self.algorithm.select(candidates, job, view)
        self._reserve_resource(chosen, job)
        return chosen

    def release_resource(self, resource_nodes: list[ResourceNode]) -> None:
        affected_nodes = {resource.node for resource in resource_nodes}
        for resource in resource_nodes:
            resource.resource_status = ResourceStatus.AVAILABLE
        for node in affected_nodes:
            self._recompute_status(node)

    def _reserve_resource(self, node: Node, job: Job) -> None:
        for req in job.requirements:
            for resource in node.free_resources(req.resource_type)[: req.amount]:
                resource.resource_status = ResourceStatus.ALLOCATED
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
