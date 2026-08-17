from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import (
    AllocationStatus,
    ClientStatus,
    JobStatus,
    NodeStatus,
    Priority,
    ResourceType,
    TopologyType,
)


class OurBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BaseOut(OurBaseModel):
    detail: str
    status_code: int


class ClientCreate(OurBaseModel):
    owner: str = Field(min_length=1)
    institute_id: int


class ClientOut(BaseOut):
    client_id: int
    owner: str
    institute_id: int
    client_status: ClientStatus


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


class JobListItemOut(OurBaseModel):
    job_id: int
    client_id: int
    status: JobStatus
    priority: Priority
    duration: int
    submitted_at: datetime


class ResourceRequirementOut(OurBaseModel):
    resource_type: ResourceType
    amount: int


class JobDetailOut(OurBaseModel):
    job_id: int
    client_id: int
    status: JobStatus
    priority: Priority
    duration: int
    submitted_at: datetime
    requirements: list[ResourceRequirementOut]


class JobEventOut(OurBaseModel):
    event_type: JobStatus
    time: datetime
    comment: str


class InstituteCreate(OurBaseModel):
    institute_name: str = Field(min_length=1)


class InstituteOut(BaseOut):
    institute_id: int
    institute_name: str


class InstituteListItemOut(OurBaseModel):
    institute_id: int
    institute_name: str


class ClientListItemOut(OurBaseModel):
    client_id: int
    owner: str
    institute_id: int
    client_status: ClientStatus


class QuotaCreate(OurBaseModel):
    institute_id: int
    resource_type: ResourceType
    limit: int = Field(gt=0)
    period: datetime | None = None  # which calendar month this limit applies to; defaults to the current month


class QuotaOut(BaseOut):
    id: int
    institute_id: int
    resource_type: ResourceType
    limit: int
    period: datetime


class ReservationCreate(OurBaseModel):
    institute_id: int
    cluster_id: int
    node_ids: list[int] = Field(min_length=1)
    start_period: datetime
    end_period: datetime
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_period(self):
        if self.end_period <= self.start_period:
            raise ValueError("end_period must be after start_period")
        return self


class ReservationOut(BaseOut):
    id: int
    institute_id: int
    cluster_id: int
    start_period: datetime
    end_period: datetime
    reason: str
    node_ids: list[int]


class ResourceCountIn(OurBaseModel):
    resource_type: ResourceType
    count: int = Field(gt=0)


class ClusterNodeSpec(OurBaseModel):
    coordinates: list[int]
    resources: list[ResourceCountIn] = Field(min_length=1)


class ClusterCreate(OurBaseModel):
    cluster_name: str = Field(min_length=1)
    topology_type: TopologyType
    dimension: list[int] = Field(min_length=1)
    wrap: bool = False
    nodes: list[ClusterNodeSpec] = Field(min_length=1)


class NodeResourceOut(OurBaseModel):
    resource_type: ResourceType
    total: int
    free: int


class NodeOut(OurBaseModel):
    node_id: int
    coordinates: list[int]
    status: NodeStatus
    resources: list[NodeResourceOut]


class ClusterOut(OurBaseModel):
    cluster_id: int
    cluster_name: str
    topology_type: TopologyType
    dimension: list[int]
    wrap: bool
    total_capacity: int
    free_capacity: int


class ClusterDetailOut(ClusterOut):
    nodes: list[NodeOut]
