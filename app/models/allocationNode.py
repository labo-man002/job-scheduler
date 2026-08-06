from sqlalchemy import Column, ForeignKey, Integer
<<<<<<< HEAD
from sqlalchemy.orm import relationship
=======
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base


class AllocationNode(Base):
    __tablename__ = "allocation_node"

    allocation_node_id = Column(Integer, primary_key=True)
    allocation_id = Column(Integer, ForeignKey("allocation.allocation_id"), nullable=False)
    resource_node_id = Column(
        Integer, ForeignKey("node_resource.resource_node_id"), nullable=False
    )
<<<<<<< HEAD

    allocation = relationship("Allocation", back_populates="allocation_nodes")
    resource_node = relationship("ResourceNode", back_populates="allocation_nodes")
=======
>>>>>>> 34ff04a (Align database models with ERD design)
