"""Read-only GPU candidate discovery against the existing SQLAlchemy Node model."""

from dataclasses import dataclass

from app.enums.nodeStatus import NodeStatus
from app.enums.resourceType import ResourceType
from app.models.node import Node

from .link import NetworkPath
from .topology import LeafSpineTopology
from .types import InconsistentInventoryError


@dataclass(frozen=True, slots=True)
class GpuCandidate:
    server_id: str
    node_id: int
    free_gpu_ids: tuple[int, ...]
    path: NetworkPath

    @property
    def free_gpu_count(self) -> int:
        return len(self.free_gpu_ids)


class GpuCandidateFinder:
    """Discovers candidates; does not allocate, mutate, flush, or query the DB."""

    def __init__(self, topology: LeafSpineTopology):
        self.topology = topology

    def find_candidates(
        self, root_switch_id: str, nodes: list[Node], *,
        min_free_gpus_per_server: int = 1,
        min_link_capacity_gbps: float | None = None,
        max_total_latency_us: float | None = None,
    ) -> tuple[GpuCandidate, ...]:
        if type(min_free_gpus_per_server) is not int or min_free_gpus_per_server < 1:
            raise ValueError("min_free_gpus_per_server must be a positive integer")
        # Validate root and constraints even for an empty server inventory.
        self.topology.get_switch(root_switch_id)
        node_by_id = {}
        for node in nodes:
            if node.node_id in node_by_id:
                raise InconsistentInventoryError(f"duplicate compute Node ID {node.node_id}")
            node_by_id[node.node_id] = node
        candidates = []
        for server in self.topology.servers():
            if server.node_id not in node_by_id:
                raise InconsistentInventoryError(f"GPU server {server.id} refers to missing Node {server.node_id}")
            node = node_by_id[server.node_id]
            if node.status == NodeStatus.DOWN:
                continue
            gpu_ids = tuple(sorted(resource.resource_node_id for resource in node.free_resources(ResourceType.GPU)))
            if len(gpu_ids) < min_free_gpus_per_server:
                continue
            path = self.topology.find_path(
                root_switch_id, server.id,
                min_link_capacity_gbps=min_link_capacity_gbps,
                max_total_latency_us=max_total_latency_us,
            )
            if path is not None:
                candidates.append(GpuCandidate(server.id, node.node_id, gpu_ids, path))
        return tuple(sorted(candidates, key=lambda c: (c.path.total_latency_us, c.node_id, c.server_id)))
