from sqlalchemy import Boolean, Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY

from app.database import Base
from app.enums.topologyType import TopologyType


class Cluster(Base):
    __tablename__ = "cluster"

    cluster_id = Column(Integer, primary_key=True)
    cluster_name = Column(String, nullable=False)
    topology_type= Column(Enum(TopologyType, name="topology_type"), nullable=False)
    dimension = Column(ARRAY(Integer), nullable=False)
    wrap = Column(Boolean, nullable=False, default=False)
