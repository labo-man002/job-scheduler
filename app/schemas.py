<<<<<<< HEAD
from pydantic import BaseModel


class OurBaseModel(BaseModel):
    class Config:
        from_attributes = True


class BaseOut(OurBaseModel):
    detail: str
    status_code: int
=======




from datetime import datetime 

from pydantic import BaseModel

from app.enums.clientStatus import ClientStatus
from app.enums.jobStatus import JobStatus
from app.enums.priority import Priority


class OurBaseModel(BaseModel):
    class Config :
        form_attributes = True


class ClientCreate(OurBaseModel):
    owner :str 
    client_status:ClientStatus

class JobCreate(OurBaseModel):
    status :JobStatus
    priority :Priority
    duration :int

class InstituteCreate(OurBaseModel):
    institute_name:str
    
class InstituteOuT(InstituteCreate):
   institute_id :int

class ClientOut(OurBaseModel):
    client_id :int 

class ClientOut(OurBaseModel):
    client_id :int 


class JobOut(OurBaseModel):
    job_id :int 
    submitted_at:datetime


class BaseOut(OurBaseModel):
   detail:str
   status_code :int
>>>>>>> ade3474 (add basic crud ,shemas and routers)
