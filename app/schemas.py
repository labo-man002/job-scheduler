from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import AllocationStatus, JobStatus, Priority, ResourceType


class OurBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BaseOut(OurBaseModel):
    detail: str
    status_code: int


class ResourceRequirementIn(OurBaseModel):
    resource_type: ResourceType
    amount: int = Field(gt=0)


class JobCreate(OurBaseModel):
    client_id: int
    priority: Priority = Priority.NORMAL
    duration: int = Field(gt=0)
    requirements: list[ResourceRequirementIn] = Field(min_length=1)


class JobOut(BaseOut):
    job_id: int
    status: JobStatus


class AllocationNodeOut(OurBaseModel):
    resource_node_id: int
    node_id: int
    resource_type: ResourceType


class AllocationOut(BaseOut):
    allocation_id: int
    job_id: int
    allocation_status: AllocationStatus
    begin_time: datetime
    end_time: datetime | None
    duration: int | None  # minutes; only known once the job stops running
    resource_nodes: list[AllocationNodeOut]
