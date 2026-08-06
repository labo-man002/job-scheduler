from sqlalchemy import Column, Enum, ForeignKey, Integer

from app.database import Base
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType


class ResourceNode(Base):
    __tablename__ = "node_resource"

    resource_node_id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("node.node_id"), nullable=False)
    resource_type_id = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    resource_type_index = Column(Integer, nullable=False)
    resource_status_id = Column(
        Enum(ResourceStatus, name="resource_status"),
        nullable=False,
        default=ResourceStatus.AVAILABLE,
    )
