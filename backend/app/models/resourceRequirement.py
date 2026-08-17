from sqlalchemy import Column, Enum, ForeignKey, Integer

from app.database import Base
from app.enums.resourceType import ResourceType


class ResourceRequirement(Base):
    __tablename__ = "resource_requirement"

    req_res_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("job.job_id"), nullable=False)
    resource_type= Column(Enum(ResourceType, name="resource_type"), nullable=False)
    amount = Column(Integer, nullable=False)
