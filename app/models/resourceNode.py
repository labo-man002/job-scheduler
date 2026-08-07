<<<<<<< HEAD
<<<<<<< HEAD
from sqlalchemy import Column, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
=======

from sqlalchemy import Column, Enum, ForeignKey, Integer, String
>>>>>>> 1d3c52a (Start coding)
=======
from sqlalchemy import Column, Enum, ForeignKey, Integer
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType


<<<<<<< HEAD
<<<<<<< HEAD
class ResourceNode(Base):
    __tablename__ = "node_resource"

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
=======

class ResourceNode(Base):
    __tablename__ = "resourceNode"
    
    id = Column(Integer ,primary_key=True)
    node_id = Column(ForeignKey("node.id") ,nullable=False)
    resource_type =Column(Enum(ResourceType) ,nullable=False)
    resource_type_index =Column(Integer ,nullable=False)
    resource_status = Column(Enum(ResourceStatus) ,nullable=False ,default=ResourceStatus.AVAILABLE)
>>>>>>> 1d3c52a (Start coding)
=======
class ResourceNode(Base):
    __tablename__ = "node_resource"

    resource_node_id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("node.node_id"), nullable=False)
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    resource_type_index = Column(Integer, nullable=False)
    resource_status = Column(
        Enum(ResourceStatus, name="resource_status"),
        nullable=False,
        default=ResourceStatus.AVAILABLE,
    )
>>>>>>> 34ff04a (Align database models with ERD design)
