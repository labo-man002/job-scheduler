from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class Reservation(Base):
    __tablename__ = "reservation"
    __table_args__ = (
        CheckConstraint("end_period > start_period", name="ck_reservation_valid_period"),
    )

    id = Column(Integer, primary_key=True)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    start_period = Column(DateTime(timezone=True), nullable=False)
    end_period = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
