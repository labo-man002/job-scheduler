from sqlalchemy import Column, Integer, String

from app.database import Base


class Institute(Base):
    __tablename__ = "institute"

    institute_id = Column(Integer, primary_key=True)
    institute_name = Column(String, nullable=False)
