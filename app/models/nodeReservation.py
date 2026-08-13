from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class NodeReservation(Base):
    __tablename__ = "node_reservation"

    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("node.node_id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservation.id"), nullable=False)

    node = relationship("Node", back_populates="node_reservations")
    reservation = relationship("Reservation", back_populates="node_reservations")
