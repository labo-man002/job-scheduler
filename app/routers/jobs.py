from fastapi import APIRouter, HTTPException

from app import schemas
from app.dependencies import DbDep
from app.domain.server import ClientNotFoundError, JobNotFoundError, JobNotRunningError, JobTooLargeError, Server

router = APIRouter(prefix="/jobs", tags=["Jobs"])


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
