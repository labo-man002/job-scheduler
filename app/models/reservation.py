from sqlalchemy import Column, DateTime, ForeignKey, Integer

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservation"

    id = Column(Integer, primary_key=True)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    start_period = Column(DateTime(timezone=True), nullable=False)
    end_period = Column(DateTime(timezone=True), nullable=False)
