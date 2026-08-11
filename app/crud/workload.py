




from sqlalchemy.orm import Session

from app import models
from app.schemas import ClientCreate, InstituteCreate, JobCreate


def get_institute(db: Session, id: int):
    return db.query(models.Institute).filter(models.Institute.id == id).first()


def add_institute(db:Session ,institute:InstituteCreate):
 institute_data = institute.model_dump()

 db_institute = models.Institute(**institute_data)
 db.add(db_institute)
 db.flush()    
 db.refresh(db_institute)  
 db.commit()

 return db_institute

async def add_client(db:Session ,client :ClientCreate):
     client_data = client.model_dump()

     db_client = models.Institute(**client_data)
     db.add(db_client)
     db.flush()    
     db.refresh(db_client)  
     db.commit()

     return db_client

async def add_Job(db:Session ,job :JobCreate):
     Job_data = job.model_dump()

     db_Job = models.Job(**Job_data)
     db.add(db_Job)
     db.flush()    
     db.refresh(db_Job)  
     db.commit()

     return db_Job