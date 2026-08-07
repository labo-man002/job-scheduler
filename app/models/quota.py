<<<<<<< HEAD
<<<<<<< HEAD
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
=======
from sqlalchemy import Column, Enum, ForeignKey, Integer
>>>>>>> 34ff04a (Align database models with ERD design)
=======
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
>>>>>>> 4cfca51 (modifing and reviewing models and enum)

from app.database import Base
from app.enums.resourceType import ResourceType


class Quota(Base):
    __tablename__ = "quota"

    id = Column(Integer, primary_key=True)
<<<<<<< HEAD
<<<<<<< HEAD
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(DateTime, nullable=False)

    institute = relationship("Institute", back_populates="quotas")
=======
    resource_type_id = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.group_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(Integer, nullable=False)
>>>>>>> 34ff04a (Align database models with ERD design)
=======
    resource_type = Column(Enum(ResourceType, name="resource_type"), nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    limit = Column(Integer, nullable=False)
    period = Column(DateTime, nullable=False)
>>>>>>> 4cfca51 (modifing and reviewing models and enum)
