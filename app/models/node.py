from sqlalchemy import Column, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import ARRAY

from app.database import Base
from app.enums.nodeStatus import NodeStatus


class Node(Base):
    __tablename__ = "node"

    node_id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey("cluster.cluster_id"), nullable=False)
    coordinates = Column(ARRAY(Integer), nullable=False)
    status_id = Column(
        Enum(NodeStatus, name="node_status"), nullable=False, default=NodeStatus.IDLE
    )
