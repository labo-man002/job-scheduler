from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.exceptions import (
    ClientNotFoundError,
    JobNotFoundError,
    JobNotRunningError,
    JobTooLargeError,
    QuotaExceededError,
)
from app.domain.server import Server
from app.enums import JobStatus

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[schemas.JobListItemOut])
def list_jobs(db: DbDep, client_id: int | None = None, status: JobStatus | None = None):
    return Server(db).list_jobs(client_id=client_id, status=status)


@router.get("/{job_id}", response_model=schemas.JobDetailOut)
def get_job(job_id: int, db: DbDep):
    try:
        job = Server(db).get_job(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Job {error} not found") from error

    return schemas.JobDetailOut(
        job_id=job.job_id,
        client_id=job.client_id,
        status=job.status,
        priority=job.priority,
        duration=job.duration,
        submitted_at=job.submitted_at,
        requirements=[
            schemas.ResourceRequirementOut(resource_type=r.resource_type, amount=r.amount) for r in job.requirements
        ],
    )


@router.get("/{job_id}/events", response_model=list[schemas.JobEventOut])
def get_job_events(job_id: int, db: DbDep):
    try:
        events = Server(db).get_job_events(job_id)
    except JobNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Job {error} not found") from error

    return [schemas.JobEventOut(event_type=e.event_type, time=e.time, comment=e.comment) for e in events]


@router.post("", response_model=schemas.JobOut, status_code=201)
def submit_job(payload: schemas.JobCreate, db: DbDep):
    server = Server(db)
    try:
        job = server.submit_job(
            client_id=payload.client_id,
            requirements=[(r.resource_type, r.amount) for r in payload.requirements],
            priority=payload.priority,
            duration=payload.duration,
        )
        db.commit()
    except ClientNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Client {error} not found") from error
    except JobTooLargeError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"No cluster has enough capacity for {error} units") from error
    except QuotaExceededError as error:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:  # e.g. duplicate resource_type across requirements
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error

    db.refresh(job)
    return schemas.JobOut(job_id=job.job_id, status=job.status, detail="Job submitted", status_code=201)


@router.delete("/{job_id}", response_model=schemas.BaseOut)
def cancel_job(job_id: int, db: DbDep):
    server = Server(db)
    try:
        server.cancel_job(job_id)
        db.commit()
    except JobNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Job {error} not found") from error

    return schemas.BaseOut(detail="Job cancelled", status_code=200)


@router.patch("/{job_id}/complete", response_model=schemas.BaseOut)
def complete_job(job_id: int, db: DbDep):
    server = Server(db)
    try:
        server.complete_job(job_id)
        db.commit()
    except JobNotFoundError as error:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Job {error} not found") from error
    except JobNotRunningError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Job {error} is not running") from error

    return schemas.BaseOut(detail="Job completed", status_code=200)


@router.get("/{job_id}/allocation", response_model=schemas.AllocationOut)
def get_allocation(job_id: int, db: DbDep):
    allocation = Server(db).get_allocation_details(job_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail=f"No allocation for job {job_id}")

    return schemas.AllocationOut(
        allocation_id=allocation.allocation_id,
        job_id=allocation.job_id,
        allocation_status=allocation.allocation_status,
        begin_time=allocation.begin_time,
        end_time=allocation.end_time,
        duration=allocation.duration,
        resource_nodes=[
            schemas.AllocationNodeOut(
                resource_node_id=an.resource_node.resource_node_id,
                node_id=an.resource_node.node_id,
                resource_type=an.resource_node.resource_type,
            )
            for an in allocation.allocation_nodes
        ],
        detail="Allocation found",
        status_code=200,
    )
