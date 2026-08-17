from sqlalchemy import Boolean, Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.resourceStatus import ResourceStatus
from app.enums.topologyType import TopologyType


class Cluster(Base):
    __tablename__ = "cluster"

    cluster_id = Column(Integer, primary_key=True)
    cluster_name = Column(String, nullable=False)
    topology_type= Column(Enum(TopologyType, name="topology_type"), nullable=False)
    dimension = Column(ARRAY(Integer), nullable=False)
    wrap = Column(Boolean, nullable=False, default=False)

    nodes = relationship("Node", back_populates="cluster")

    def total_capacity(self) -> int:
        return sum(len(node.resources) for node in self.nodes)

    def free_capacity(self) -> int:
        return sum(
            1
            for node in self.nodes
            for resource in node.resources
            if resource.resource_status == ResourceStatus.AVAILABLE
        )
