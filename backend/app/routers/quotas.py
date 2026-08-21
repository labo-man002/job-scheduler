from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import InstituteNotFoundError, QuotaNotFoundError
from app.domain.server import Server

router = APIRouter(prefix="/quotas", tags=["Quotas"])


@router.post("", response_model=schemas.QuotaOut, status_code=201)
def create_quota(payload: schemas.QuotaCreate, db: DbDep):
    server = Server(db)
    try:
        quota = server.create_quota(
            institute_id=payload.institute_id, resource_type=payload.resource_type,
            limit=payload.limit, period=payload.period,
        )
        db.commit()
    except InstituteNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Institute {error} not found") from error

    db.refresh(quota)
    return schemas.QuotaOut(
        id=quota.id,
        institute_id=quota.institute_id,
        resource_type=quota.resource_type,
        limit=quota.limit,
        period=quota.period,
        detail="Quota set",
        status_code=201,
    )


@router.get("", response_model=list[schemas.QuotaListItemOut])
def list_quotas(db: DbDep, institute_id: int | None = None):
    return Server(db).list_quotas(institute_id=institute_id)


@router.delete("/{quota_id}", response_model=schemas.BaseOut)
def delete_quota(quota_id: int, db: DbDep):
    server = Server(db)
    try:
        server.delete_quota(quota_id)
        db.commit()
    except QuotaNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Quota {error} not found") from error

    return schemas.BaseOut(detail="Quota deleted", status_code=200)
