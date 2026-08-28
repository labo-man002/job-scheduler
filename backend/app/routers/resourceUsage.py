from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import InstituteNotFoundError
from app.domain.server import Server

router = APIRouter(prefix="/resource-usage", tags=["Resource usage"])


@router.get("/institutes/{institute_id}", response_model=list[schemas.ResourceUsageOut])
def list_resource_usage(institute_id: int, db: DbDep, period: int | None = None):
    try:
        return Server(db).list_resource_usage(institute_id, period)
    except InstituteNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Institute {error} not found") from error
