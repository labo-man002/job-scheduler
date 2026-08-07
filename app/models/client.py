<<<<<<< HEAD
<<<<<<< HEAD
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
=======



=======
>>>>>>> 34ff04a (Align database models with ERD design)
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
>>>>>>> 1d3c52a (Start coding)

from app.database import Base
from app.enums.clientStatus import ClientStatus


class Client(Base):
    __tablename__ = "client"

<<<<<<< HEAD
<<<<<<< HEAD
    client_id = Column(Integer, primary_key=True)
    owner = Column(String, nullable=False)
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    client_status = Column(
=======
    client_id = Column(Integer, primary_key=True)
    owner = Column(String, nullable=False)
<<<<<<< HEAD
    group_id = Column(Integer, ForeignKey("groups.group_id"), nullable=False)
    client_status_id = Column(
>>>>>>> 34ff04a (Align database models with ERD design)
=======
    institute_id = Column(Integer, ForeignKey("institute.institute_id"), nullable=False)
    client_status = Column(
>>>>>>> 4cfca51 (modifing and reviewing models and enum)
        Enum(ClientStatus, name="client_status"),
        nullable=False,
        default=ClientStatus.OFFLINE,
    )
<<<<<<< HEAD

    institute = relationship("Institute", back_populates="clients")
    jobs = relationship("Job", back_populates="client")
=======
    id = Column(Integer ,primary_key=True)
    owner = Column(String ,nullable=False)
    group_id = Column(Integer ,ForeignKey("group.id"),nullable=False)
    client_status = Column(Enum(ClientStatus) ,nullable=False ,default=ClientStatus.OFFLINE)
>>>>>>> 1d3c52a (Start coding)
=======
>>>>>>> 34ff04a (Align database models with ERD design)
