from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Institute(Base):
    __tablename__ = "institute"

    institute_id = Column(Integer, primary_key=True)
    institute_name = Column(String, nullable=False)

    clients = relationship("Client", back_populates="institute")
    quotas = relationship("Quota", back_populates="institute")
    reservations = relationship("Reservation", back_populates="institute")
    resource_usages = relationship("ResourceUsage", back_populates="institute")
