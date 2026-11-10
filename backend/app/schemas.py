from datetime import datetime
from typing import Literal

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
    min_nodes: int = Field(default=1, ge=1)
    max_nodes: int | None = Field(default=None, ge=1)
    require_full_connectivity: bool = False
    min_bandwidth_gbps: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    max_latency_us: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    requirements: list[ResourceRequirementIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_node_range(self):
        if self.max_nodes is not None and self.max_nodes < self.min_nodes:
            raise ValueError("max_nodes must be greater than or equal to min_nodes")
        return self


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
    min_nodes: int
    max_nodes: int | None
    require_full_connectivity: bool
    min_bandwidth_gbps: float | None
    max_latency_us: float | None
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
    coordinates: list[int] = Field(default_factory=list)
    nic_capacity_gbps: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    nic_state: Literal["UP", "DOWN"] = "UP"
    resources: list[ResourceCountIn] = Field(min_length=1)


class LeafSpinePortGroupIn(OurBaseModel):
    count: int = Field(gt=0)
    speed_gbps: float = Field(gt=0, allow_inf_nan=False)


class LeafSpinePortStateIn(OurBaseModel):
    number: int = Field(gt=0)
    state: Literal["UP", "DOWN"]


class LeafSpineSwitchIn(OurBaseModel):
    switch_id: str = Field(min_length=1)
    role: Literal["LEAF", "SPINE"]
    state: Literal["UP", "DOWN"] = "UP"
    ports: list[LeafSpinePortStateIn] = Field(default_factory=list)
    model: str = Field(min_length=1)
    port_groups: list[LeafSpinePortGroupIn] = Field(min_length=1)


class LeafSpineEndpointIn(OurBaseModel):
    device_kind: Literal["SWITCH", "NODE"]
    device_id: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)


class LeafSpineLinkIn(OurBaseModel):
    link_id: str | None = None
    a: LeafSpineEndpointIn
    b: LeafSpineEndpointIn
    capacity_gbps: float = Field(gt=0, allow_inf_nan=False)
    latency_us: float = Field(ge=0, allow_inf_nan=False)
    state: Literal["UP", "DOWN"] = "UP"


class LeafSpineFabricIn(OurBaseModel):
    switches: list[LeafSpineSwitchIn] = Field(min_length=1)
    links: list[LeafSpineLinkIn] = Field(default_factory=list)


class ClusterCreate(OurBaseModel):
    cluster_name: str = Field(min_length=1)
    topology_type: TopologyType
    dimension: list[int] = Field(default_factory=list)
    wrap: bool = False
    fabric: LeafSpineFabricIn | None = None
    nodes: list[ClusterNodeSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_topology_config(self):
        if self.topology_type == TopologyType.LEAF_SPINE:
            if self.dimension or self.wrap:
                raise ValueError("LEAF_SPINE does not use grid dimensions or wrap")
            if self.fabric is None:
                raise ValueError("LEAF_SPINE requires a fabric configuration")
            if any(node.nic_capacity_gbps is None for node in self.nodes):
                raise ValueError("every LEAF_SPINE compute Node requires nic_capacity_gbps")
        elif self.fabric is not None:
            raise ValueError("fabric configuration is only valid for LEAF_SPINE clusters")
        return self


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
