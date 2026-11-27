from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal, engine
from app.main import app
from app.models import ReplayRun
from app.routers import replay_runs


def submit(client, **payload):
    return client.post("/replay/runs", json={"request_id": str(uuid4()), **payload})


def fail_engine(*_args):
    raise AssertionError("Opening a saved run must not invoke replay")


def test_reopen_is_exact_and_reuse_freezes_the_original_trace(monkeypatch):
    client = TestClient(app)
    created = submit(client, preset="oracle")
    assert created.status_code == 201
    original = created.json()
    run_id = original["id"]
    result = original["outputs"]
    assert original["created_at"].endswith("Z")
    assert original["inputs"]["topology"] == {"kind": "linear"}
    assert original["inputs"]["queue_policies"] == ["fifo", "priority"]
    assert original["gpus_per_node"] == [2]
    assert len(original["inputs"]["config_sha256"]) == len(original["inputs"]["trace_sha256"]) == 64
    assert [job["wait"] for job in result["runs"][0]["jobs"]] == [0, 4, 11]
    assert [job["finish"] for job in result["runs"][1]["jobs"]] == [5, 14, 6]
    assert result["runs"][0]["events"][0] == {"tick": 0, "kind": "arrival", "job_id": 1}
    assert result["runs"][0]["metrics"]["allocated_gpu_ticks"] == result["comparison"]["fifo"]["allocated_gpu_ticks"] == 27
    assert result["comparison"]["fifo"]["available_gpu_ticks"] == 28
    assert result["comparison"]["fifo"]["occupancy"] == 27 / 28

    with monkeypatch.context() as context:
        context.setattr(replay_runs, "run_replay", fail_engine)
        assert TestClient(app).get(f"/replay/runs/{run_id}").json() == original

    with monkeypatch.context() as context:
        context.setattr(replay_runs, "load_preset", fail_engine)
        fork = submit(client, starting_run_id=run_id, gpus_per_node=[3])
    assert fork.status_code == 201
    fork = fork.json()
    assert fork["id"] != run_id
    assert fork["gpus_per_node"] == [3]
    assert fork["inputs"]["scenario"]["jobs"] == original["inputs"]["scenario"]["jobs"]
    assert fork["inputs"]["trace_sha256"] == original["inputs"]["trace_sha256"]
    assert fork["inputs"]["config_sha256"] != original["inputs"]["config_sha256"]

    renamed = client.patch(f"/replay/runs/{run_id}", json={"display_name": "  Original experiment  "})
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Original experiment"
    assert client.get(f"/replay/runs/{run_id}").json() == {**original, "display_name": "Original experiment"}
    assert client.patch(f"/replay/runs/{run_id}", json={"display_name": None}).json()["display_name"] is None
    assert client.get("/replay/oracle").status_code == 200


def test_concurrent_retry_and_fresh_key(monkeypatch):
    client = TestClient(app)
    payload = {"request_id": str(uuid4()), "preset": "oracle"}
    started = Event()
    release = Event()
    calls = []
    real_engine = replay_runs.run_replay

    def track_engine(scenario, policy):
        calls.append(policy)
        if policy == "fifo":
            started.set()
            assert release.wait(timeout=10)
        return real_engine(scenario, policy)

    monkeypatch.setattr(replay_runs, "run_replay", track_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, "/replay/runs", json=payload)
        try:
            assert started.wait(timeout=10)
            second = pool.submit(client.post, "/replay/runs", json=payload)
        finally:
            release.set()
        responses = (first.result(timeout=10), second.result(timeout=10))
    assert [response.status_code for response in responses] == [201, 200]
    assert responses[0].json() == responses[1].json()
    assert calls == ["fifo", "priority"]

    assert client.post("/replay/runs", json=payload).json()["id"] == responses[0].json()["id"]
    assert client.post("/replay/runs", json={**payload, "gpus_per_node": [3]}).status_code == 409
    assert calls == ["fifo", "priority"]
    assert submit(client, preset="oracle").json()["id"] != responses[0].json()["id"]
    with SessionLocal() as db:
        found = db.scalars(select(ReplayRun).where(ReplayRun.request_id == payload["request_id"])).all()
        assert len(found) == 1


def test_run_failures_leave_no_partial_snapshot(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    request_id = str(uuid4())
    payload = {"request_id": request_id, "preset": "oracle"}
    assert client.post("/replay/runs", json={**payload, "gpus_per_node": [0]}).status_code == 422
    assert client.post("/replay/runs", json={**payload, "scenario": {}}).status_code == 422

    real_engine = replay_runs.run_replay

    def fail_second_policy(scenario, policy):
        if policy == "priority":
            raise RuntimeError("second policy failed")
        return real_engine(scenario, policy)

    with monkeypatch.context() as context:
        context.setattr(replay_runs, "run_replay", fail_second_policy)
        assert client.post("/replay/runs", json=payload).status_code == 500

    def fail_insert(_conn, _cursor, statement, *_args):
        if statement.startswith("INSERT INTO replay_runs"):
            raise SQLAlchemyError("write failed")

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        assert client.post("/replay/runs", json=payload).status_code == 500
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)

    with SessionLocal() as db:
        assert db.scalar(select(ReplayRun).where(ReplayRun.request_id == request_id)) is None
    assert client.post("/replay/runs", json=payload).status_code == 201


def test_history_pagination_and_legacy_open(monkeypatch):
    client = TestClient(app)
    ids = [submit(client, preset="oracle").json()["id"] for _ in range(2)]
    with SessionLocal() as db:
        for run_id in ids:
            row = db.get(ReplayRun, run_id)
            row.created_at = datetime(2040, 1, 1, tzinfo=timezone.utc)
        db.commit()

    page_one = client.get("/replay/runs?limit=1").json()
    newest, oldest = sorted(ids, reverse=True)
    assert page_one["items"][0]["id"] == newest
    assert page_one["next_offset"] == 1
    assert "inputs" not in page_one["items"][0] and "outputs" not in page_one["items"][0]
    assert client.get("/replay/runs?limit=1&offset=1").json()["items"][0]["id"] == oldest

    fresh = submit(client, preset="oracle").json()
    with SessionLocal() as db:
        row = db.get(ReplayRun, fresh["id"])
        row.created_at = datetime(2041, 1, 1, tzinfo=timezone.utc)
        row.inputs = {**row.inputs, "schema_version": 999}
        db.commit()

    cursor = page_one["next_before_id"]
    assert client.get(f"/replay/runs?limit=1&before_id={cursor}").json()["items"][0]["id"] == oldest
    assert client.get("/replay/runs?limit=1").json()["items"][0]["can_reuse"] is False
    monkeypatch.setattr(replay_runs, "run_replay", fail_engine)
    old_snapshot = client.get(f"/replay/runs/{fresh['id']}").json()
    assert old_snapshot["can_reuse"] is False
    assert old_snapshot["outputs"] == fresh["outputs"]
    assert submit(client, starting_run_id=fresh["id"]).status_code == 409
    assert client.get(f"/replay/runs/{uuid4()}").status_code == 404
