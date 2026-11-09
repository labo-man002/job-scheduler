from math import isfinite

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, validates

from app.database import Base
from app.enums.nodeStatus import NodeStatus
from app.enums.operationalState import OperationalState
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType


class Node(Base):
    __tablename__ = "node"

    node_id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey("cluster.cluster_id"), nullable=False)
    coordinates = Column(ARRAY(Integer), nullable=False)
    # Optional physical NIC metadata used by the in-memory leaf-spine fabric.
    nic_capacity_gbps = Column(Float, nullable=True)
    nic_state = Column(Enum(OperationalState, name="operational_state"), nullable=False, default=OperationalState.UP)

    status= Column(
        Enum(NodeStatus, name="node_status"), nullable=False, default=NodeStatus.IDLE
    )

    resources = relationship("ResourceNode", back_populates="node")
    cluster = relationship("Cluster", back_populates="nodes")
    node_reservations = relationship("NodeReservation", back_populates="node")


    @validates("nic_capacity_gbps")
    def _check_nic_capacity(self, _key, capacity):
        if capacity is not None and (
            isinstance(capacity, bool)
            or not isinstance(capacity, (int, float))
            or not isfinite(capacity)
            or capacity <= 0
        ):
            raise ValueError("NIC capacity must be finite and positive")
        return float(capacity) if capacity is not None else None

    @validates("nic_state")
    def _check_nic_state(self, _key, state):
        if not isinstance(state, OperationalState):
            raise ValueError("nic_state must be an OperationalState")
        return state

    @validates("coordinates")
    def _check_coordinates(self, _key, coordinates):
        if self.cluster is None:
            return coordinates
        dims = self.cluster.dimension
        if len(coordinates) != len(dims):
            raise ValueError("coordinates/dimension length mismatch")
        if any(not (0 <= c < dims[axis]) for axis, c in enumerate(coordinates)):
            raise ValueError("coordinate out of bounds")
        return coordinates

    def free_resources(self, resource_type: ResourceType) -> list:
        return [
            r
            for r in self.resources
            if r.resource_type == resource_type and r.resource_status == ResourceStatus.AVAILABLE
        ]

    def resource_summary(self) -> list[dict]:
        """One row per resource_type present on this node, with total/free counts -- the
        per-node breakdown a topology/resource-availability view needs."""
        present = {r.resource_type for r in self.resources}
        return [
            {
                "resource_type": resource_type,
                "total": sum(1 for r in self.resources if r.resource_type == resource_type),
                "free": len(self.free_resources(resource_type)),
            }
            for resource_type in present
        ]
