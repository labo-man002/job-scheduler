from sqlalchemy import Column, Enum, ForeignKey, Integer

from app.database import Base
from app.enums.resourceType import ResourceType


class Quota(Base):
    __tablename__ = "quota"

    id = Column(Integer, primary_key=True)
    resource_type_id = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.group_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(Integer, nullable=False)
