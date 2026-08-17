from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.enums.clientStatus import ClientStatus


class Client(Base):
    __tablename__ = "client"

    client_id = Column(Integer, primary_key=True)
    owner = Column(String, nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    client_status = Column(
        Enum(ClientStatus, name="client_status"),
        nullable=False,
        default=ClientStatus.OFFLINE,
    )

    institute = relationship("Institute", back_populates="clients")
    jobs = relationship("Job", back_populates="client")
