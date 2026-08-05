
from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
from app.enums.priority import Priority


class Job(Base):
    __tablename__ = "job"

    id = Column(Integer ,primary_key=True)
    client_id = Column(Integer ,ForeignKey("client.id"),nullable=False)
    priority_status = Column(Enum(Priority) ,nullable=False ,default=Priority.Normal)
    duration = Column(Integer ,nullable=False)