from sqlalchemy import Column, Enum, ForeignKey, Integer

from app.database import Base
from app.enums.resourceType import ResourceType


class ResourceUsage(Base):
    __tablename__ = "resource_usage"

    id = Column(Integer, primary_key=True)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    resource_type= Column(Enum(ResourceType, name="resource_type"), nullable=False)
    consumed_hours = Column(Integer, nullable=False)
    period = Column(Integer, nullable=False)
