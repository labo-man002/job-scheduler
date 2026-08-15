from sqlalchemy import Column, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship, validates

from app.database import Base
from app.enums.nodeStatus import NodeStatus
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType


class Node(Base):
    __tablename__ = "node"

    node_id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey("cluster.cluster_id"), nullable=False)
    coordinates = Column(ARRAY(Integer), nullable=False)
    status= Column(
        Enum(NodeStatus, name="node_status"), nullable=False, default=NodeStatus.IDLE
    )

    resources = relationship("ResourceNode", back_populates="node")
    cluster = relationship("Cluster", back_populates="nodes")
    node_reservations = relationship("NodeReservation", back_populates="node")

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
