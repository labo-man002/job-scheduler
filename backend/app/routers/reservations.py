from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import (
    ClusterNotFoundError,
    InstituteNotFoundError,
    NodeNotFoundError,
    NodeNotInClusterError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from app.domain.server import Server

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post("", response_model=schemas.ReservationOut, status_code=201)
def create_reservation(payload: schemas.ReservationCreate, db: DbDep):
    server = Server(db)
    try:
        reservation = server.create_reservation(
            institute_id=payload.institute_id,
            cluster_id=payload.cluster_id,
            node_ids=payload.node_ids,
            start_period=payload.start_period,
            end_period=payload.end_period,
            reason=payload.reason,
        )
        db.commit()
    except InstituteNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Institute {error} not found") from error
    except ClusterNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Cluster {error} not found") from error
    except NodeNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Node(s) not found: {error}") from error
    except NodeNotInClusterError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ReservationConflictError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error

    db.refresh(reservation)
    return schemas.ReservationOut(
        id=reservation.id,
        institute_id=reservation.institute_id,
        cluster_id=payload.cluster_id,
        start_period=reservation.start_period,
        end_period=reservation.end_period,
        reason=reservation.reason,
        node_ids=payload.node_ids,
        detail="Reservation created",
        status_code=201,
    )


@router.delete("/{reservation_id}", response_model=schemas.BaseOut)
def cancel_reservation(reservation_id: int, db: DbDep):
    server = Server(db)
    try:
        server.cancel_reservation(reservation_id)
        db.commit()
    except ReservationNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Reservation {error} not found") from error

    return schemas.BaseOut(detail="Reservation cancelled", status_code=200)
