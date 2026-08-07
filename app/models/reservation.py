<<<<<<< HEAD
<<<<<<< HEAD
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship
=======
from sqlalchemy import Column, DateTime, ForeignKey, Integer
>>>>>>> 34ff04a (Align database models with ERD design)
=======
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
>>>>>>> d6abd73 (update models and enums)

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservation"
<<<<<<< HEAD
<<<<<<< HEAD
    __table_args__ = (
        CheckConstraint("end_period > start_period", name="ck_reservation_valid_period"),
    )
=======
>>>>>>> 34ff04a (Align database models with ERD design)
=======
    __table_args__ = (
        CheckConstraint("end_period > start_period", name="ck_reservation_valid_period"),
    )
>>>>>>> d6abd73 (update models and enums)

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.group_id"), nullable=False)
    start_period = Column(DateTime(timezone=True), nullable=False)
    end_period = Column(DateTime(timezone=True), nullable=False)
<<<<<<< HEAD
<<<<<<< HEAD
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    institute = relationship("Institute", back_populates="reservations")
    node_reservations = relationship("NodeReservation", back_populates="reservation")
=======
>>>>>>> 34ff04a (Align database models with ERD design)
=======
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
<<<<<<< HEAD
    created_by = Column(String, nullable=False)
>>>>>>> d6abd73 (update models and enums)
=======
>>>>>>> 709543e (configure alembic)
