"""Versioned inputs for the small, fixed-duration replay."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, model_validator

from app.enums.priority import Priority

# Bound individual time values without imposing a short experiment horizon.
MAX_TIME_VALUE = 2**32 - 1
# Each device becomes a separate ORM object. Keep fixture inventory bounded.
MAX_NODE_GPUS = 1024

PositiveInt = Annotated[StrictInt, Field(gt=0)]
Tick = Annotated[StrictInt, Field(ge=0, le=MAX_TIME_VALUE)]
PositiveTime = Annotated[StrictInt, Field(gt=0, le=MAX_TIME_VALUE)]


class ReplayInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplayNode(ReplayInput):
    id: PositiveInt
    gpus: Annotated[PositiveInt, Field(le=MAX_NODE_GPUS)]


class ReplayJob(ReplayInput):
    id: PositiveInt
    arrival: Tick
    duration: PositiveTime
    gpus: PositiveInt
    priority: Priority


class LinearTopologyInput(ReplayInput):
    kind: Literal["linear"]


class LeafUplink(ReplayInput):
    leaf: PositiveInt
    spine: PositiveInt


class NodeAttachment(ReplayInput):
    node: PositiveInt
    leaf: PositiveInt


class LeafSpineTopologyInput(ReplayInput):
    kind: Literal["leaf_spine"]
    leaves: Annotated[tuple[PositiveInt, ...], Field(min_length=1, max_length=4)]
    uplinks: Annotated[tuple[LeafUplink, ...], Field(max_length=16)]
    attachments: Annotated[tuple[NodeAttachment, ...], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def validate_fabric(self):
        leaves = set(self.leaves)
        if len(leaves) != len(self.leaves):
            raise ValueError("leaf IDs must be unique")
        if any(link.leaf not in leaves for link in (*self.uplinks, *self.attachments)):
            raise ValueError("all links must reference a declared leaf")
        if len({(link.leaf, link.spine) for link in self.uplinks}) != len(self.uplinks):
            raise ValueError("leaf-spine uplinks must be unique")
        if len({link.spine for link in self.uplinks}) > 4:
            raise ValueError("fabric supports up to four spines")
        if len({link.node for link in self.attachments}) != len(self.attachments):
            raise ValueError("each node must be attached once")
        return self


ReplayTopology = Annotated[LinearTopologyInput | LeafSpineTopologyInput, Field(discriminator="kind")]


class Scenario(ReplayInput):
    schema_version: Annotated[StrictInt, Field(ge=1, le=2)]
    source: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    seconds_per_tick: PositiveTime
    nodes: Annotated[tuple[ReplayNode, ...], Field(min_length=1, max_length=4)]
    jobs: Annotated[tuple[ReplayJob, ...], Field(min_length=1)]
    topology: ReplayTopology | None = None

    @property
    def effective_topology(self) -> LinearTopologyInput | LeafSpineTopologyInput:
        return self.topology if self.topology is not None else LinearTopologyInput(kind="linear")

    @model_validator(mode="after")
    def validate_configuration(self):
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("node IDs must be unique")
        if len({job.id for job in self.jobs}) != len(self.jobs):
            raise ValueError("job IDs must be unique")
        if self.schema_version == 1 and self.topology is not None:
            raise ValueError("explicit topology requires schema_version 2")
        if self.schema_version == 2 and self.topology is None:
            raise ValueError("schema_version 2 requires a topology")
        if isinstance(self.topology, LeafSpineTopologyInput):
            if {link.node for link in self.topology.attachments} != node_ids:
                raise ValueError("fabric attachments must include exactly the scenario node IDs")
        return self
