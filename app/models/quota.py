<<<<<<< HEAD
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
=======
from sqlalchemy import Column, Enum, ForeignKey, Integer
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base
from app.enums.resourceType import ResourceType


class Quota(Base):
    __tablename__ = "quota"

    id = Column(Integer, primary_key=True)
<<<<<<< HEAD
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(DateTime, nullable=False)

    institute = relationship("Institute", back_populates="quotas")
=======
    resource_type_id = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(Integer, nullable=False)
>>>>>>> 34ff04a (Align database models with ERD design)
