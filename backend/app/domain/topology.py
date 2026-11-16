from app.enums.topologyType import TopologyType
from app.models.cluster import Cluster
from app.models.node import Node


class Topology:
    def __init__(self, cluster: Cluster):
        if cluster.topology_type == TopologyType.MESH_2D and cluster.wrap:
            raise ValueError("MESH_2D cannot have wrap=True")
        self.cluster = cluster

    def build_view(self, nodes: list[Node]) -> "TopologyView":
        return TopologyView(self.cluster, nodes)


class TopologyView:
    """Disposable per-placement-attempt snapshot. Grid math (TORUS_3D/TORUS_2D/MESH_2D)
    is generic over coordinates/dimension/wrap. FAT_TREE is not a coordinate grid —
    deferred, see docs/decisions.md."""

    def __init__(self, cluster: Cluster, nodes: list[Node]):
        self.cluster = cluster
        self.nodes = nodes
        self._by_coordinates = {tuple(n.coordinates): n for n in nodes}

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
                if neighbor is not None:
                    result.append(neighbor)
        return result

    def distance(self, a: Node, b: Node) -> int:
        self._require_grid()
        dims = self.cluster.dimension
        total = 0
        for axis in range(len(dims)):
            diff = abs(a.coordinates[axis] - b.coordinates[axis])
            if self.cluster.wrap:
                diff = min(diff, dims[axis] - diff)
            total += diff
        return total

    def _require_grid(self) -> None:
        if self.cluster.topology_type == TopologyType.FAT_TREE:
            raise NotImplementedError(
                "FAT_TREE has no coordinate-grid distance model yet — see docs/decisions.md"
            )
