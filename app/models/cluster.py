<<<<<<< HEAD
<<<<<<< HEAD
from sqlalchemy import Boolean, Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
=======


from ctypes import Array

from sqlalchemy import Column, Enum, ForeignKey, Integer, String
>>>>>>> 1d3c52a (Start coding)
=======
from sqlalchemy import Boolean, Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
>>>>>>> 34ff04a (Align database models with ERD design)

from app.database import Base
from app.enums.topologyType import TopologyType


<<<<<<< HEAD
<<<<<<< HEAD
class Cluster(Base):
    __tablename__ = "cluster"

    cluster_id = Column(Integer, primary_key=True)
    cluster_name = Column(String, nullable=False)
    topology_type= Column(Enum(TopologyType, name="topology_type"), nullable=False)
    dimension = Column(ARRAY(Integer), nullable=False)
    wrap = Column(Boolean, nullable=False, default=False)

    nodes = relationship("Node", back_populates="cluster")
=======
class Client(Base):
    __tablename__ = "cluster"

    id = Column(Integer ,primary_key=True)
    cluster_name = Column(String ,nullable=False)
    wrap =Column(bool)
    topology_type =Column(Enum(TopologyType))
    dimenstion = Column(Array())
>>>>>>> 1d3c52a (Start coding)
=======
class Cluster(Base):
    __tablename__ = "cluster"

    cluster_id = Column(Integer, primary_key=True)
    cluster_name = Column(String, nullable=False)
    topology_type_id = Column(Enum(TopologyType, name="topology_type"), nullable=False)
    dimension = Column(ARRAY(Integer), nullable=False)
    wrap = Column(Boolean, nullable=False, default=False)
>>>>>>> 34ff04a (Align database models with ERD design)
