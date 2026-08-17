from sqlalchemy import Column, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType


class ResourceNode(Base):
    __tablename__ = "node_resource"
    __table_args__ = (
        UniqueConstraint("node_id", "resource_type", "resource_type_index", name="uq_node_resource_type_index"),
    )

    resource_node_id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("node.node_id"), nullable=False)
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    resource_type_index = Column(Integer, nullable=False)
    resource_status = Column(
        Enum(ResourceStatus, name="resource_status"),
        nullable=False,
        default=ResourceStatus.AVAILABLE,
    )

    node = relationship("Node", back_populates="resources")
    allocation_nodes = relationship("AllocationNode", back_populates="resource_node")
