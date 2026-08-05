


from sqlalchemy import Column, Integer, String

from app.database import Base


class Group(Base):
      __tablename__ ="group"

      id = Column(Integer ,primary_key=True)
      name = Column(String ,nullable=False)
      