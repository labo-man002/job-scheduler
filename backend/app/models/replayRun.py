from sqlalchemy import Column, DateTime, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB

from app.orm_base import Base


class ReplayRun(Base):
    __tablename__ = "replay_runs"

    id = Column(Uuid, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    display_name = Column(String(120), nullable=True)
    request_id = Column(Uuid, nullable=False, unique=True)
    workload_label = Column(String, nullable=False)
    source = Column(String, nullable=False)
    gpus_per_node = Column(JSONB, nullable=False)
    inputs = Column(JSONB, nullable=False)
    outputs = Column(JSONB, nullable=False)
    input_hash = Column(String(64), nullable=False)


Index("ix_replay_runs_newest", ReplayRun.created_at.desc(), ReplayRun.id.desc())
