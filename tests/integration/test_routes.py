"""End-to-end HTTP tests via TestClient. Routes call db.commit() themselves,
so the plain flush-and-rollback fixture other integration tests use isn't
enough to isolate them -- this uses a SAVEPOINT so an inner commit() only
commits to the savepoint, and the real transaction never lands, regardless
of how many times a route commits."""

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal, engine, get_db
from app.main import app

from .db_factories import create_cluster_with_nodes, create_institute_and_client


@pytest.fixture
def db():
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("Postgres not reachable — check .env and that the DB is running")

    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def seeded_cluster(db):
    """Default size: 4 nodes * 2 CPUs = 8 total capacity. Use db_factories
    directly in a test that needs a different size."""
    _, client = create_institute_and_client(db)
    create_cluster_with_nodes(db, node_count=4, resources_per_node=2)
    db.commit()  # exercise the same savepoint-restart path a route's commit() would

    return {"client_id": client.client_id}


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_submit_job_returns_201_and_running_status(api_client, db, seeded_cluster):
    resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "RUNNING"
    assert isinstance(body["job_id"], int)


def test_submit_job_unknown_client_returns_404(api_client, db):
    resp = api_client.post("/jobs", json={
        "client_id": 999999,
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 1}],
    })
    assert resp.status_code == 404


@pytest.mark.parametrize("bad_payload", [
    {"duration": 10, "requirements": []},  # no requirements at all
    {"duration": 10, "requirements": [{"resource_type": "CPU", "amount": 0}]},  # zero amount
    {"duration": 0, "requirements": [{"resource_type": "CPU", "amount": 1}]},  # zero duration
])
def test_submit_job_rejects_invalid_payloads(api_client, db, seeded_cluster, bad_payload):
    resp = api_client.post("/jobs", json={"client_id": seeded_cluster["client_id"], "priority": "NORMAL", **bad_payload})
    assert resp.status_code == 422


def test_get_allocation_after_submit(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    alloc_resp = api_client.get(f"/jobs/{job_id}/allocation")
    assert alloc_resp.status_code == 200, alloc_resp.text
    body = alloc_resp.json()
    assert body["job_id"] == job_id
    assert len(body["resource_nodes"]) == 2


def test_get_allocation_404_when_none(api_client, db, seeded_cluster):
    api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 8}],  # fills the cluster
    })
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],  # queues, no allocation
    })
    job_id = submit_resp.json()["job_id"]

    alloc_resp = api_client.get(f"/jobs/{job_id}/allocation")
    assert alloc_resp.status_code == 404


def test_submit_job_too_large_for_any_cluster_returns_422(api_client, db, seeded_cluster):
    resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 100}],  # exceeds total cluster capacity (8)
    })
    assert resp.status_code == 422


def test_cancel_job_returns_200(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    cancel_resp = api_client.delete(f"/jobs/{job_id}")
    assert cancel_resp.status_code == 200


def test_cancel_unknown_job_returns_404(api_client, db):
    resp = api_client.delete("/jobs/999999")
    assert resp.status_code == 404


def test_complete_job_returns_200_and_sets_duration(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    complete_resp = api_client.patch(f"/jobs/{job_id}/complete")
    assert complete_resp.status_code == 200

    alloc_resp = api_client.get(f"/jobs/{job_id}/allocation")
    body = alloc_resp.json()
    assert body["end_time"] is not None
    assert body["duration"] is not None


def test_complete_job_not_running_returns_409(api_client, db, seeded_cluster):
    api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 8}],  # fills the cluster
    })
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],  # queues, never runs
    })
    job_id = submit_resp.json()["job_id"]

    resp = api_client.patch(f"/jobs/{job_id}/complete")
    assert resp.status_code == 409


def test_complete_unknown_job_returns_404(api_client, db):
    resp = api_client.patch("/jobs/999999/complete")
    assert resp.status_code == 404


def test_docs_lists_all_routes(api_client):
    resp = api_client.get("/openapi.json")
    paths = resp.json()["paths"]
    assert "/jobs" in paths and "post" in paths["/jobs"]
    assert "/jobs/{job_id}" in paths and "delete" in paths["/jobs/{job_id}"]
    assert "/jobs/{job_id}/allocation" in paths and "get" in paths["/jobs/{job_id}/allocation"]
    assert "/jobs/{job_id}/complete" in paths and "patch" in paths["/jobs/{job_id}/complete"]
