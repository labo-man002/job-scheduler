

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings



<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 709543e (configure alembic)
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{settings.database_username}:"
    f"{settings.database_password}@"
    f"{settings.database_hostname}:"
    f"{settings.database_port}/"
    f"{settings.database_name}"
)
<<<<<<< HEAD
=======
SQLALCHEMY_DATABASE_URL = f'postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}/{settings.database_name}'

>>>>>>> 1d3c52a (Start coding)
=======
>>>>>>> 709543e (configure alembic)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        