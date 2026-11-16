from abc import ABC, abstractmethod

from app.enums.nodeStatus import NodeStatus
from app.models.job import Job
from app.models.node import Node

from .topology import TopologyView


class PlaceAlgorithm(ABC):
    @abstractmethod
    def select(self, candidates: list[Node], job: Job, view: TopologyView) -> Node:
        raise NotImplementedError

    @abstractmethod
    def rank(self, candidates: list[Node], job: Job, view: TopologyView) -> list[Node]:
        """candidates ordered by preference, best first. select() is rank()[0]."""
        raise NotImplementedError


class PackAlgorithm(PlaceAlgorithm):
    def select(self, candidates: list[Node], job: Job, view: TopologyView) -> Node:
        return self.rank(candidates, job, view)[0]

    def rank(self, candidates: list[Node], job: Job, view: TopologyView) -> list[Node]:
        occupied = [n for n in view.nodes if n.status in (NodeStatus.ALLOCATED, NodeStatus.MIXED)]
        if not occupied:
            # No occupied node anywhere yet — deterministic fallback: lowest node_id.
            return sorted(candidates, key=lambda n: n.node_id)
        return sorted(
            candidates,
            key=lambda n: (min(view.distance(n, o) for o in occupied), n.node_id),
        )


class SpreadAlgorithm(PlaceAlgorithm):
    def select(self, candidates: list[Node], job: Job, view: TopologyView) -> Node:
        return self.rank(candidates, job, view)[0]

    def rank(self, candidates: list[Node], job: Job, view: TopologyView) -> list[Node]:
        occupied = [n for n in view.nodes if n.status in (NodeStatus.ALLOCATED, NodeStatus.MIXED)]
        if not occupied:
            # No occupied node anywhere yet — deterministic fallback: lowest node_id.
            return sorted(candidates, key=lambda n: n.node_id)
        return sorted(
            candidates,
            key=lambda n: (-min(view.distance(n, o) for o in occupied), n.node_id),
        )
