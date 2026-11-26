

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .orm_base import Base as Base

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{settings.database_username}:"
    f"{settings.database_password}@"
    f"{settings.database_hostname}:"
    f"{settings.database_port}/"
    f"{settings.database_name}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        