

from ctypes import Array

from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
from app.enums.topologyType import TopologyType


class Client(Base):
    __tablename__ = "cluster"

    id = Column(Integer ,primary_key=True)
    cluster_name = Column(String ,nullable=False)
    wrap =Column(bool)
    topology_type =Column(Enum(TopologyType))
    dimenstion = Column(Array())