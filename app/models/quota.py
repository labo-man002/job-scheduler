from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer

from app.database import Base
from app.enums.resourceType import ResourceType


class Quota(Base):
    __tablename__ = "quota"

    id = Column(Integer, primary_key=True)
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(DateTime, nullable=False)
