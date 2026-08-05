


from sqlalchemy import Column, Enum, ForeignKey, Integer, String

from app.database import Base
from app.enums.clientStatus import ClientStatus


class Client(Base):
    __tablename__ = "client"

    id = Column(Integer ,primary_key=True)
    owner = Column(String ,nullable=False)
    group_id = Column(Integer ,ForeignKey("group.id"),nullable=False)
    client_status = Column(Enum(ClientStatus) ,nullable=False ,default=ClientStatus.OFFLINE)