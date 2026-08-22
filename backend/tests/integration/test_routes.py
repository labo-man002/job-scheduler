"""End-to-end HTTP tests via TestClient. Routes call db.commit() themselves,
so the plain flush-and-rollback fixture other integration tests use isn't
enough to isolate them -- this uses a SAVEPOINT so an inner commit() only
commits to the savepoint, and the real transaction never lands, regardless
of how many times a route commits."""

from datetime import datetime, timedelta, timezone

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
    institute, client = create_institute_and_client(db)
    cluster, nodes = create_cluster_with_nodes(db, node_count=4, resources_per_node=2)
    db.commit()  # exercise the same savepoint-restart path a route's commit() would

    return {
        "client_id": client.client_id,
        "institute_id": institute.institute_id,
        "cluster_id": cluster.cluster_id,
        "nodes": nodes,
    }


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_register_client_returns_201(api_client, db, seeded_cluster):
    resp = api_client.post("/clients", json={"owner": "bob", "institute_id": seeded_cluster["institute_id"]})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["owner"] == "bob"
    assert body["client_status"] == "OFFLINE"
    assert isinstance(body["client_id"], int)


def test_register_client_unknown_institute_returns_404(api_client, db):
    resp = api_client.post("/clients", json={"owner": "bob", "institute_id": 999999})
    assert resp.status_code == 404


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


def test_submit_job_duplicate_resource_type_returns_422(api_client, db, seeded_cluster):
    resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"],
        "priority": "NORMAL",
        "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}, {"resource_type": "CPU", "amount": 3}],
    })
    assert resp.status_code == 422


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


def test_register_institute_returns_201(api_client, db):
    resp = api_client.post("/institutes", json={"institute_name": "New Institute"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["institute_name"] == "New Institute"


def test_create_cluster_returns_201_with_nodes(api_client, db):
    resp = api_client.post("/clusters", json={
        "cluster_name": "api-cluster",
        "topology_type": "RING",
        "dimension": [2],
        "wrap": True,
        "nodes": [
            {"coordinates": [0], "resources": [{"resource_type": "CPU", "count": 2}]},
            {"coordinates": [1], "resources": [{"resource_type": "CPU", "count": 2}]},
        ],
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total_capacity"] == 4
    assert body["free_capacity"] == 4
    assert len(body["nodes"]) == 2


def test_create_cluster_bad_coordinates_returns_422(api_client, db):
    resp = api_client.post("/clusters", json={
        "cluster_name": "bad-cluster",
        "topology_type": "RING",
        "dimension": [2],
        "wrap": True,
        "nodes": [{"coordinates": [0, 0], "resources": [{"resource_type": "CPU", "count": 1}]}],
    })
    assert resp.status_code == 422


def test_list_and_get_cluster(api_client, db, seeded_cluster):
    resp = api_client.post("/clusters", json={
        "cluster_name": "listed-cluster",
        "topology_type": "RING",
        "dimension": [1],
        "wrap": True,
        "nodes": [{"coordinates": [0], "resources": [{"resource_type": "CPU", "count": 1}]}],
    })
    cluster_id = resp.json()["cluster_id"]

    list_resp = api_client.get("/clusters")
    assert list_resp.status_code == 200
    assert cluster_id in [c["cluster_id"] for c in list_resp.json()]

    detail_resp = api_client.get(f"/clusters/{cluster_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["cluster_id"] == cluster_id


def test_get_unknown_cluster_returns_404(api_client, db):
    resp = api_client.get("/clusters/999999")
    assert resp.status_code == 404


def test_create_quota_returns_201(api_client, db, seeded_cluster):
    resp = api_client.post("/quotas", json={
        "institute_id": seeded_cluster["institute_id"], "resource_type": "CPU", "limit": 4,
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["limit"] == 4


def test_create_quota_unknown_institute_returns_404(api_client, db):
    resp = api_client.post("/quotas", json={"institute_id": 999999, "resource_type": "CPU", "limit": 4})
    assert resp.status_code == 404


def test_create_reservation_returns_201(api_client, db, seeded_cluster):
    resp = api_client.post("/reservations", json={
        "institute_id": seeded_cluster["institute_id"],
        "cluster_id": seeded_cluster["cluster_id"],
        "node_ids": [seeded_cluster["nodes"][0].node_id],
        "start_period": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "end_period": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "reason": "maintenance",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["node_ids"] == [seeded_cluster["nodes"][0].node_id]


def test_create_reservation_node_from_other_cluster_returns_422(api_client, db, seeded_cluster):
    other_cluster, _ = create_cluster_with_nodes(db, node_count=1, resources_per_node=1, cluster_name="other-cluster")
    db.commit()

    resp = api_client.post("/reservations", json={
        "institute_id": seeded_cluster["institute_id"],
        "cluster_id": other_cluster.cluster_id,
        "node_ids": [seeded_cluster["nodes"][0].node_id],  # belongs to seeded_cluster, not other_cluster
        "start_period": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "end_period": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "reason": "maintenance",
    })
    assert resp.status_code == 422


def test_create_reservation_bad_period_returns_422(api_client, db, seeded_cluster):
    resp = api_client.post("/reservations", json={
        "institute_id": seeded_cluster["institute_id"],
        "cluster_id": seeded_cluster["cluster_id"],
        "node_ids": [seeded_cluster["nodes"][0].node_id],
        "start_period": datetime.now(timezone.utc).isoformat(),
        "end_period": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "reason": "bad",
    })
    assert resp.status_code == 422


def test_list_jobs(api_client, db, seeded_cluster):
    api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"], "priority": "NORMAL", "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })

    resp = api_client.get("/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    filtered = api_client.get("/jobs", params={"client_id": seeded_cluster["client_id"], "status": "RUNNING"})
    assert filtered.status_code == 200
    assert all(j["status"] == "RUNNING" for j in filtered.json())


def test_get_job_returns_detail_with_requirements(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"], "priority": "NORMAL", "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    resp = api_client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["requirements"] == [{"resource_type": "CPU", "amount": 2}]


def test_get_job_unknown_returns_404(api_client, db):
    resp = api_client.get("/jobs/999999")
    assert resp.status_code == 404


def test_get_job_events_returns_history(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"], "priority": "NORMAL", "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    resp = api_client.get(f"/jobs/{job_id}/events")
    assert resp.status_code == 200, resp.text
    event_types = [e["event_type"] for e in resp.json()]
    assert event_types == ["QUEUED", "RUNNING"]


def test_list_recent_events_returns_events_across_jobs_newest_first(api_client, db, seeded_cluster):
    submit_resp = api_client.post("/jobs", json={
        "client_id": seeded_cluster["client_id"], "priority": "NORMAL", "duration": 10,
        "requirements": [{"resource_type": "CPU", "amount": 2}],
    })
    job_id = submit_resp.json()["job_id"]

    resp = api_client.get("/jobs/events/recent", params={"limit": 5})
    assert resp.status_code == 200, resp.text
    events = resp.json()
    assert events[0]["job_id"] == job_id
    assert events[0]["event_type"] == "RUNNING"
    assert events[1]["job_id"] == job_id
    assert events[1]["event_type"] == "QUEUED"


def test_list_and_get_institute(api_client, db, seeded_cluster):
    list_resp = api_client.get("/institutes")
    assert list_resp.status_code == 200
    assert seeded_cluster["institute_id"] in [i["institute_id"] for i in list_resp.json()]

    get_resp = api_client.get(f"/institutes/{seeded_cluster['institute_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["institute_id"] == seeded_cluster["institute_id"]


def test_get_institute_unknown_returns_404(api_client, db):
    resp = api_client.get("/institutes/999999")
    assert resp.status_code == 404


def test_list_and_get_client(api_client, db, seeded_cluster):
    list_resp = api_client.get("/clients", params={"institute_id": seeded_cluster["institute_id"]})
    assert list_resp.status_code == 200
    assert seeded_cluster["client_id"] in [c["client_id"] for c in list_resp.json()]

    get_resp = api_client.get(f"/clients/{seeded_cluster['client_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["client_id"] == seeded_cluster["client_id"]


def test_get_client_unknown_returns_404(api_client, db):
    resp = api_client.get("/clients/999999")
    assert resp.status_code == 404


def test_delete_quota_returns_200(api_client, db, seeded_cluster):
    create_resp = api_client.post("/quotas", json={
        "institute_id": seeded_cluster["institute_id"], "resource_type": "CPU", "limit": 4,
    })
    quota_id = create_resp.json()["id"]

    resp = api_client.delete(f"/quotas/{quota_id}")
    assert resp.status_code == 200


def test_delete_quota_unknown_returns_404(api_client, db):
    resp = api_client.delete("/quotas/999999")
    assert resp.status_code == 404


def test_cancel_reservation_returns_200(api_client, db, seeded_cluster):
    create_resp = api_client.post("/reservations", json={
        "institute_id": seeded_cluster["institute_id"],
        "cluster_id": seeded_cluster["cluster_id"],
        "node_ids": [seeded_cluster["nodes"][0].node_id],
        "start_period": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "end_period": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "reason": "maintenance",
    })
    reservation_id = create_resp.json()["id"]

    resp = api_client.delete(f"/reservations/{reservation_id}")
    assert resp.status_code == 200


def test_cancel_reservation_unknown_returns_404(api_client, db):
    resp = api_client.delete("/reservations/999999")
    assert resp.status_code == 404


def test_set_node_down_returns_200(api_client, db, seeded_cluster):
    node_id = seeded_cluster["nodes"][0].node_id
    resp = api_client.patch(f"/nodes/{node_id}/down")
    assert resp.status_code == 200, resp.text


def test_set_node_down_unknown_node_returns_404(api_client, db):
    resp = api_client.patch("/nodes/999999/down")
    assert resp.status_code == 404


def test_docs_lists_all_routes(api_client):
    resp = api_client.get("/openapi.json")
    paths = resp.json()["paths"]
    assert "/jobs" in paths and "post" in paths["/jobs"] and "get" in paths["/jobs"]
    assert "/jobs/{job_id}" in paths and "delete" in paths["/jobs/{job_id}"] and "get" in paths["/jobs/{job_id}"]
    assert "/jobs/{job_id}/allocation" in paths and "get" in paths["/jobs/{job_id}/allocation"]
    assert "/jobs/{job_id}/complete" in paths and "patch" in paths["/jobs/{job_id}/complete"]
    assert "/jobs/{job_id}/events" in paths and "get" in paths["/jobs/{job_id}/events"]
    assert "/clients" in paths and "post" in paths["/clients"] and "get" in paths["/clients"]
    assert "/clients/{client_id}" in paths and "get" in paths["/clients/{client_id}"]
    assert "/institutes" in paths and "post" in paths["/institutes"] and "get" in paths["/institutes"]
    assert "/institutes/{institute_id}" in paths and "get" in paths["/institutes/{institute_id}"]
    assert "/clusters" in paths and "post" in paths["/clusters"] and "get" in paths["/clusters"]
    assert "/clusters/{cluster_id}" in paths and "get" in paths["/clusters/{cluster_id}"]
    assert "/nodes/{node_id}/down" in paths and "patch" in paths["/nodes/{node_id}/down"]
    assert "/quotas" in paths and "post" in paths["/quotas"] and "delete" in paths["/quotas/{quota_id}"]
    assert "/reservations" in paths and "post" in paths["/reservations"]
    assert "delete" in paths["/reservations/{reservation_id}"]
