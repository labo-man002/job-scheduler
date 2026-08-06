from sqlalchemy import Column, ForeignKey, Integer
<<<<<<< HEAD
from sqlalchemy.orm import relationship
=======
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base


class NodeReservation(Base):
    __tablename__ = "node_reservation"

    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("node.node_id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservation.id"), nullable=False)
<<<<<<< HEAD

    node = relationship("Node", back_populates="node_reservations")
    reservation = relationship("Reservation", back_populates="node_reservations")
=======
>>>>>>> 34ff04a (Align database models with ERD design)
