from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import InstituteNotFoundError
from app.domain.server import Server

router = APIRouter(prefix="/institutes", tags=["Institutes"])


@router.post("", response_model=schemas.InstituteOut, status_code=201)
def register_institute(payload: schemas.InstituteCreate, db: DbDep):
    institute = Server(db).register_institute(institute_name=payload.institute_name)
    db.commit()
    db.refresh(institute)
    return schemas.InstituteOut(
        institute_id=institute.institute_id,
        institute_name=institute.institute_name,
        detail="Institute registered",
        status_code=201,
    )


@router.get("", response_model=list[schemas.InstituteListItemOut])
def list_institutes(db: DbDep):
    return Server(db).list_institutes()


@router.get("/{institute_id}", response_model=schemas.InstituteListItemOut)
def get_institute(institute_id: int, db: DbDep):
    try:
        return Server(db).get_institute(institute_id)
    except InstituteNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Institute {error} not found") from error
