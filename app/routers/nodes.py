from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import NodeNotFoundError
from app.domain.server import Server

router = APIRouter(prefix="/nodes", tags=["Nodes"])


@router.patch("/{node_id}/down", response_model=schemas.BaseOut)
def set_node_down(node_id: int, db: DbDep):
    server = Server(db)
    try:
        server.set_node_down(node_id)
        db.commit()
    except NodeNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Node {error} not found") from error

    return schemas.BaseOut(detail="Node marked down", status_code=200)
