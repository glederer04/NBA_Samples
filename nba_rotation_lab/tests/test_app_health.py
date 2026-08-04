"""Tests for the production health endpoint."""

import duckdb
import pytest

import app as application
from rotation_lab.config import DEMO_DATABASE_PATH


def connect_demo_database(*, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the same populated database used by the production deployment."""

    return duckdb.connect(
        database=str(DEMO_DATABASE_PATH),
        read_only=read_only,
    )


def test_health_check_reports_ready_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The health endpoint should validate the application database."""

    monkeypatch.setattr(
        application,
        "connect_database",
        connect_demo_database,
    )
    client = application.server.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "database": "ready",
        "status": "ok",
    }
