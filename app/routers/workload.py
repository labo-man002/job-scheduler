





from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.crud.workload import add_institute
from app.database import get_db


router = APIRouter(
    tags=["Scheduling"]
)  

DbDep = Annotated[Session ,Depends(get_db)]

@router.post("/institute" ,response_model=schemas.InstituteOuT)
def add(ins:schemas.InstituteCreate ,db:DbDep):
   try:
       
      add_institute(db=db, institute=ins)
   except Exception as e:
        db.rollback()
        return schemas.BaseOut(status_code=500, detail="failed")
    
   return schemas.BaseOut(status_code=201, detail="success")
  