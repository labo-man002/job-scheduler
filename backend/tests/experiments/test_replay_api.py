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
