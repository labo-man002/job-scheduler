from sqlalchemy import Column, Integer, String

from app.database import Base


class Group(Base):
    __tablename__ = "groups"

    group_id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)
