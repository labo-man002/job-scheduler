"""Versioned inputs for the small, fixed-duration replay."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, model_validator

from app.enums.priority import Priority

PositiveInt = Annotated[StrictInt, Field(gt=0)]
Tick = Annotated[StrictInt, Field(ge=0)]


class ReplayInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplayNode(ReplayInput):
    id: PositiveInt
    gpus: PositiveInt


class ReplayJob(ReplayInput):
    id: PositiveInt
    arrival: Tick
    duration: PositiveInt
    gpus: PositiveInt
    priority: Priority


class Scenario(ReplayInput):
    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    source: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    seconds_per_tick: PositiveInt
    nodes: Annotated[tuple[ReplayNode, ...], Field(min_length=1, max_length=4)]
    jobs: Annotated[tuple[ReplayJob, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_ids(self):
        if len({node.id for node in self.nodes}) != len(self.nodes):
            raise ValueError("node IDs must be unique")
        if len({job.id for job in self.jobs}) != len(self.jobs):
            raise ValueError("job IDs must be unique")
        return self
