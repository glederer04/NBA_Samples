"""Tests for the production health endpoint."""

from app import server


def test_health_check_reports_ready_database() -> None:
    """The health endpoint should validate the application database."""

    client = server.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "database": "ready",
        "status": "ok",
    }
