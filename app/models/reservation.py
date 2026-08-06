<<<<<<< HEAD
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
=======
from sqlalchemy import Column, DateTime, ForeignKey, Integer
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservation"
<<<<<<< HEAD
    __table_args__ = (
        CheckConstraint("end_period > start_period", name="ck_reservation_valid_period"),
    )
=======
>>>>>>> 34ff04a (Align database models with ERD design)

    id = Column(Integer, primary_key=True)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    start_period = Column(DateTime(timezone=True), nullable=False)
    end_period = Column(DateTime(timezone=True), nullable=False)
<<<<<<< HEAD
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    institute = relationship("Institute", back_populates="reservations")
    node_reservations = relationship("NodeReservation", back_populates="reservation")
=======
>>>>>>> 34ff04a (Align database models with ERD design)
