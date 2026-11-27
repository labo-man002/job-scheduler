"""Persist and retrieve paired experiment runs for the single-user web instance."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, model_validator
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.dependencies import DbDep
from app.experiments.__main__ import canonical_hash, git_provenance
from app.experiments.replay import run_replay
from app.experiments.replay_input import ReplayTopology, Scenario
from app.models import ReplayRun

from .replay import Comparison, NodeCapacities, ScenarioName, compare_outputs, configure_scenario, load_preset

router = APIRouter(prefix="/replay/runs", tags=["replay"])
POLICIES = ("fifo", "priority")
INPUT_VERSION = 1
OUTPUT_VERSION = 1
SUPPORTED_SCENARIO_VERSIONS = (1, 2)


class CreateReplayRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    preset: ScenarioName | None = None
    starting_run_id: UUID | None = None
    scenario: Scenario | None = None
    gpus_per_node: NodeCapacities | None = None
    topology: ReplayTopology | None = None

    @model_validator(mode="after")
    def require_one_source(self):
        if sum(value is not None for value in (self.preset, self.starting_run_id, self.scenario)) != 1:
            raise ValueError("Provide exactly one of preset, starting_run_id or scenario")
        return self


DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\x00]+$")]


class RenameReplayRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None


class ReplayRunSummary(BaseModel):
    id: UUID
    created_at: datetime
    display_name: str | None
    workload_label: str
    source: str
    gpus_per_node: list[int]
    can_reuse: bool


class ReplayRunInputs(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int
    scenario: dict
    workload_label: str
    topology: dict
    queue_policies: list[str]
    placement: str
    service_time: str
    trace_sha256: str
    config_sha256: str


class ReplayRunOutputs(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int
    engine_revision: str | None
    worktree_dirty: bool | None = None
    runs: list[dict]
    comparison: Comparison


class ReplayRunDetail(ReplayRunSummary):
    inputs: ReplayRunInputs
    outputs: ReplayRunOutputs


class ReplayRunPage(BaseModel):
    items: list[ReplayRunSummary]
    next_offset: int | None
    next_before_id: UUID | None = None


@contextmanager
def request_session(engine: Engine, request_id: UUID) -> Iterator[Session]:
    """Serialize retries across processes while leaving simulation outside a transaction."""
    lock_key = int(canonical_hash(str(request_id))[:16], 16) - 2**63
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        connection.commit()
        try:
            with Session(bind=connection) as session:
                yield session
        finally:
            if not connection.invalidated:
                try:
                    connection.rollback()
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
                    connection.commit()
                except Exception:
                    connection.invalidate()
                    raise


def find_run(db: Session, run_id: UUID) -> ReplayRun:
    row = db.get(ReplayRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    return row


def can_reuse(run: ReplayRun) -> bool:
    if run.inputs.get("schema_version") != INPUT_VERSION:
        return False
    try:
        Scenario.model_validate(run.inputs.get("scenario"))
    except ValidationError:
        return False
    return True


def summarize(row, *, reusable: bool) -> ReplayRunSummary:
    return ReplayRunSummary(
        id=row.id,
        created_at=row.created_at.astimezone(timezone.utc),
        display_name=row.display_name,
        workload_label=row.workload_label,
        source=row.source,
        gpus_per_node=row.gpus_per_node,
        can_reuse=reusable,
    )


def detail(row: ReplayRun) -> ReplayRunDetail:
    return ReplayRunDetail(**summarize(row, reusable=can_reuse(row)).model_dump(), inputs=row.inputs, outputs=row.outputs)


def resolve_scenario(payload: CreateReplayRun, db: Session) -> tuple[str, Scenario]:
    if payload.starting_run_id is not None:
        original = find_run(db, payload.starting_run_id)
        if not can_reuse(original):
            raise HTTPException(status_code=409, detail="This snapshot was created using a scenario version the current engine cannot reuse")
        scenario = Scenario.model_validate(original.inputs["scenario"])
        label = original.workload_label
    elif payload.preset is not None:
        scenario = load_preset(payload.preset)
        label = payload.preset
    else:
        scenario = payload.scenario
        label = scenario.source

    try:
        scenario = configure_scenario(scenario, payload.gpus_per_node, payload.topology)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors(include_url=False, include_context=False)) from error
    if "\x00" in scenario.source or "\x00" in label:
        raise HTTPException(status_code=422, detail="Workload source and label may not contain null characters")
    return label, scenario


def snapshot_inputs(workload_label: str, scenario: Scenario) -> dict:
    effective_scenario = scenario.model_dump(mode="json", exclude_none=True)
    config = {
        "seconds_per_tick": scenario.seconds_per_tick,
        "nodes": effective_scenario["nodes"],
        "topology": scenario.effective_topology.model_dump(mode="json"),
        "queue_policies": POLICIES,
        "placement": "pack",
        "service_time": "fixed",
    }
    return {
        "schema_version": INPUT_VERSION,
        "scenario": effective_scenario,
        "workload_label": workload_label,
        "topology": config["topology"],
        "queue_policies": list(POLICIES),
        "placement": config["placement"],
        "service_time": config["service_time"],
        "trace_sha256": canonical_hash(effective_scenario["jobs"]),
        "config_sha256": canonical_hash(config),
    }


def snapshot_outputs(scenario: Scenario) -> dict:
    fifo, priority = (run_replay(scenario, policy) for policy in POLICIES)
    provenance = git_provenance()
    return ReplayRunOutputs(
        schema_version=OUTPUT_VERSION,
        engine_revision=provenance["git_sha"],
        worktree_dirty=provenance["worktree_dirty"],
        runs=[fifo, priority],
        comparison=compare_outputs(scenario, fifo, priority),
    ).model_dump(mode="json")


@router.post("", status_code=201, response_model=ReplayRunDetail, responses={200: {"model": ReplayRunDetail}})
def create_run(payload: CreateReplayRun, response: Response, db: DbDep):
    with request_session(db.get_bind(), payload.request_id) as session:
        label, scenario = resolve_scenario(payload, session)
        inputs = snapshot_inputs(label, scenario)
        input_hash = canonical_hash(inputs)
        prior = session.scalar(select(ReplayRun).where(ReplayRun.request_id == payload.request_id))
        if prior is not None:
            if prior.input_hash != input_hash:
                raise HTTPException(status_code=409, detail="This request ID was already used with different inputs")
            response.status_code = 200
            return detail(prior)

        # Close the reads before the engine runs. The session-level key lock remains held.
        session.rollback()
        outputs = snapshot_outputs(scenario)
        row = ReplayRun(
            id=uuid4(),
            request_id=payload.request_id,
            input_hash=input_hash,
            workload_label=label,
            source=scenario.source,
            gpus_per_node=[node.gpus for node in scenario.nodes],
            inputs=inputs,
            outputs=outputs,
        )
        session.add(row)
        session.flush()
        result = detail(row)
        session.commit()
        return result


@router.get("", response_model=ReplayRunPage)
def list_runs(
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    before_id: UUID | None = None,
):
    reusable = (
        (ReplayRun.inputs["schema_version"].as_integer() == INPUT_VERSION)
        & ReplayRun.inputs["scenario"]["schema_version"].as_integer().in_(SUPPORTED_SCENARIO_VERSIONS)
    )
    columns = (
        ReplayRun.id, ReplayRun.created_at, ReplayRun.display_name, ReplayRun.workload_label, ReplayRun.source,
        ReplayRun.gpus_per_node, reusable.label("can_reuse"),
    )
    query = select(*columns).order_by(ReplayRun.created_at.desc(), ReplayRun.id.desc()).limit(limit + 1)
    if before_id is not None:
        anchor = db.execute(select(ReplayRun.created_at).where(ReplayRun.id == before_id)).one_or_none()
        if anchor is None:
            raise HTTPException(status_code=404, detail="Replay history page anchor not found")
        query = query.where(
            (ReplayRun.created_at < anchor.created_at) | ((ReplayRun.created_at == anchor.created_at) & (ReplayRun.id < before_id))
        )
    else:
        query = query.offset(offset)

    rows = db.execute(query).all()
    items = [summarize(row, reusable=bool(row.can_reuse)) for row in rows[:limit]]
    has_more = len(rows) > limit
    return ReplayRunPage(
        items=items,
        next_offset=offset + limit if has_more and before_id is None else None,
        next_before_id=items[-1].id if has_more else None,
    )


@router.get("/{run_id}", response_model=ReplayRunDetail)
def get_run(run_id: Annotated[UUID, Path()], db: DbDep):
    return detail(find_run(db, run_id))


@router.patch("/{run_id}", response_model=ReplayRunSummary)
def rename_run(run_id: Annotated[UUID, Path()], payload: RenameReplayRun, db: DbDep):
    row = find_run(db, run_id)
    row.display_name = payload.display_name
    response = summarize(row, reusable=can_reuse(row))
    db.commit()
    return response
