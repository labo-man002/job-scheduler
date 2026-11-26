from fastapi.testclient import TestClient

from app.main import app


def test_replay_comparison_reports_paired_job_waits():
    with TestClient(app) as client:
        result = client.get("/replay/oracle")
        assert result.status_code == 200
        comparison = result.json()
        assert comparison["fifo"]["completed"] == comparison["priority"]["completed"] == 3
        assert [(job["fifo_wait"], job["priority_wait"]) for job in comparison["jobs"]] == [(0, 0), (4, 5), (11, 3)]
        assert client.get("/replay/unknown").status_code == 422


def test_custom_capacity_applies_to_both_policies():
    with TestClient(app) as client:
        result = client.post("/replay/oracle", json={"gpus_per_node": [2, 2]})
        assert result.status_code == 200
        rows = result.json()["jobs"]
        assert [(row["fifo_wait"], row["priority_wait"]) for row in rows] == [(0, 0), (0, 0), (3, 3)]
        for invalid in ([], [0], [1025], [1] * 5):
            assert client.post("/replay/oracle", json={"gpus_per_node": invalid}).status_code == 422
