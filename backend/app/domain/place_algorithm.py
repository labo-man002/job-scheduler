from abc import ABC, abstractmethod

from app.enums.nodeStatus import NodeStatus
from app.models.job import Job
from app.models.node import Node

from .topology import PlacementTopologyView


class PlaceAlgorithm(ABC):
    @abstractmethod
    def select(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> Node:
        raise NotImplementedError

    @abstractmethod
    def rank(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> list[Node]:
        """Candidates ordered by preference, best first. select() is rank()[0]."""
        raise NotImplementedError


class PackAlgorithm(PlaceAlgorithm):
    def select(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> Node:
        return self.rank(candidates, job, view)[0]

    def rank(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> list[Node]:
        occupied = [n for n in view.nodes if n.status in (NodeStatus.ALLOCATED, NodeStatus.MIXED)]
        if not occupied:
            return sorted(candidates, key=lambda n: n.node_id)
        return sorted(
            candidates,
            key=lambda n: (min(view.distance(n, o) for o in occupied), n.node_id),
        )


class SpreadAlgorithm(PlaceAlgorithm):
    def select(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> Node:
        return self.rank(candidates, job, view)[0]

    def rank(self, candidates: list[Node], job: Job, view: PlacementTopologyView) -> list[Node]:
        occupied = [n for n in view.nodes if n.status in (NodeStatus.ALLOCATED, NodeStatus.MIXED)]
        if not occupied:
            return sorted(candidates, key=lambda n: n.node_id)
        return sorted(
            candidates,
            key=lambda n: (-min(view.distance(n, o) for o in occupied), n.node_id),
        )
