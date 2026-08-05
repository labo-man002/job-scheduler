from ctypes import Array

from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
from app.enums.nodeStatus import NodeStatus
from app.enums.priority import Priority

class Node(Base):
 __tablename__ = "nodes"
id = Column(Integer ,primary_key=True)
cluster_id = Column(Integer ,ForeignKey("cluster.id"),nullable=False)
node_status = Column(Enum(NodeStatus) ,nullable=False ,default=NodeStatus.IDLE)
coordinate = Column(Array())