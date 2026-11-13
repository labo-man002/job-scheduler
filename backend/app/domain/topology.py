"""Common placement-topology contracts and the existing coordinate-grid implementation."""

from abc import ABC, abstractmethod
from collections import deque

from app.enums.topologyType import TopologyType
from app.models.cluster import Cluster
from app.models.node import Node


class PlacementTopologyView(ABC):
    """Read-only topology snapshot consumed by placement algorithms.

    Concrete topologies own their representation. The placement layer only asks
    whether compute Nodes can communicate and how costly their connection is.
    """

    @property
    @abstractmethod
    def nodes(self) -> list[Node]:
        raise NotImplementedError

    @abstractmethod
    def is_reachable(self, a: Node, b: Node) -> bool:
        raise NotImplementedError

    @abstractmethod
    def distance(self, a: Node, b: Node) -> float:
        """Return the topology's comparable path cost; infinity means unreachable."""
        raise NotImplementedError

    def path_latency(self, a: Node, b: Node) -> float | None:
        """Physical path latency when the topology models it; otherwise None."""
        return None

    def path_bandwidth(self, a: Node, b: Node) -> float | None:
        """Nominal bottleneck bandwidth when modeled; otherwise None."""
        return None

    def path_metrics(
        self, a: Node, b: Node, *,
        min_bandwidth_gbps: float | None = None,
        max_latency_us: float | None = None,
    ) -> tuple[float, float] | None:
        """Return a path satisfying optional constraints, as (latency, bottleneck)."""
        latency = self.path_latency(a, b)
        bandwidth = self.path_bandwidth(a, b)
        if latency is None or bandwidth is None:
            return None
        if min_bandwidth_gbps is not None and bandwidth < min_bandwidth_gbps:
            return None
        if max_latency_us is not None and latency > max_latency_us:
            return None
        return latency, bandwidth


class PlacementTopology(ABC):
    """Factory for a disposable, read-only view used during one placement attempt."""

    @abstractmethod
    def build_view(self, nodes: list[Node]) -> PlacementTopologyView:
        raise NotImplementedError


class Topology(PlacementTopology):
    """Coordinate-grid topology retained for RING, MESH and TORUS clusters."""

    def __init__(self, cluster: Cluster):
        if cluster.topology_type == TopologyType.MESH_2D and cluster.wrap:
            raise ValueError("MESH_2D cannot have wrap=True")
        self.cluster = cluster

    def build_view(self, nodes: list[Node]) -> "TopologyView":
        return TopologyView(self.cluster, nodes)


class TopologyView(PlacementTopologyView):
    """Disposable grid snapshot. Grid math remains local to this implementation."""

    def __init__(self, cluster: Cluster, nodes: list[Node]):
        self.cluster = cluster
        self._nodes = nodes
        self._by_coordinates = {tuple(n.coordinates): n for n in nodes}

    @property
    def nodes(self) -> list[Node]:
        return self._nodes

    def neighbors(self, node: Node) -> list[Node]:
        self._require_grid()
        dims = self.cluster.dimension
        result = []
        for axis in range(len(dims)):
            for delta in (-1, 1):
                candidate_coords = list(node.coordinates)
                candidate_coords[axis] += delta
                if self.cluster.wrap:
                    candidate_coords[axis] %= dims[axis]
                elif not (0 <= candidate_coords[axis] < dims[axis]):
                    continue
                neighbor = self._by_coordinates.get(tuple(candidate_coords))
                if neighbor is not None and neighbor is not node and neighbor not in result:
                    result.append(neighbor)
        return sorted(result, key=lambda n: n.node_id)

    def is_reachable(self, a: Node, b: Node) -> bool:
        self._require_grid()
        if a is b:
            return True
        pending = deque([a])
        visited = {a.node_id}
        while pending:
            current = pending.popleft()
            for neighbor in self.neighbors(current):
                if neighbor.node_id == b.node_id:
                    return True
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    pending.append(neighbor)
        return False

    def distance(self, a: Node, b: Node) -> float:
        self._require_grid()
        if a is b:
            return 0
        pending = deque([(a, 0)])
        visited = {a.node_id}
        while pending:
            current, distance = pending.popleft()
            for neighbor in self.neighbors(current):
                if neighbor.node_id == b.node_id:
                    return distance + 1
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    pending.append((neighbor, distance + 1))
        return float("inf")

    def _require_grid(self) -> None:
        if self.cluster.topology_type == TopologyType.FAT_TREE:
            raise NotImplementedError(
                "FAT_TREE has no coordinate-grid distance model yet — see docs/decisions.md"
            )
