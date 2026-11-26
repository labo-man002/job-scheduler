"""Versioned inputs for the small, fixed-duration replay."""

from typing import Annotated

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


class Scenario(ReplayInput):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    source: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    seconds_per_tick: PositiveTime
    nodes: Annotated[tuple[ReplayNode, ...], Field(min_length=1, max_length=4)]
    jobs: Annotated[tuple[ReplayJob, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_ids(self):
        if len({node.id for node in self.nodes}) != len(self.nodes):
            raise ValueError("node IDs must be unique")
        if len({job.id for job in self.jobs}) != len(self.jobs):
            raise ValueError("job IDs must be unique")
        return self
