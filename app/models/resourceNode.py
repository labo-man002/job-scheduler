
from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
from app.enums.resourceStatus import ResourceStatus
from app.enums.resourceType import ResourceType



class ResourceNode(Base):
    __tablename__ = "resourceNode"
    
    id = Column(Integer ,primary_key=True)
    node_id = Column(ForeignKey("node.id") ,nullable=False)
    resource_type =Column(Enum(ResourceType) ,nullable=False)
    resource_type_index =Column(Integer ,nullable=False)
    resource_status = Column(Enum(ResourceStatus) ,nullable=False ,default=ResourceStatus.AVAILABLE)