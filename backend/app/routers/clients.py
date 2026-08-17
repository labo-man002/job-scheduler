from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import ClientNotFoundError, InstituteNotFoundError
from app.domain.server import Server

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("", response_model=schemas.ClientOut, status_code=201)
def register_client(payload: schemas.ClientCreate, db: DbDep):
    server = Server(db)
    try:
        client = server.register_client(owner=payload.owner, institute_id=payload.institute_id)
        db.commit()
    except InstituteNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Institute {error} not found") from error

    db.refresh(client)
    return schemas.ClientOut(
        client_id=client.client_id,
        owner=client.owner,
        institute_id=client.institute_id,
        client_status=client.client_status,
        detail="Client registered",
        status_code=201,
    )


@router.get("", response_model=list[schemas.ClientListItemOut])
def list_clients(db: DbDep, institute_id: int | None = None):
    return Server(db).list_clients(institute_id=institute_id)


@router.get("/{client_id}", response_model=schemas.ClientListItemOut)
def get_client(client_id: int, db: DbDep):
    try:
        return Server(db).get_client(client_id)
    except ClientNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Client {error} not found") from error
