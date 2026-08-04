"""Tests for environment-aware project configuration."""

from pathlib import Path

from rotation_lab.config import (
    DEFAULT_DATABASE_PATH,
    PROJECT_ROOT,
    resolve_database_path,
)


def test_resolve_database_path_uses_local_default() -> None:
    """An empty override should preserve the local development database."""

    assert resolve_database_path("") == DEFAULT_DATABASE_PATH


def test_resolve_database_path_handles_project_relative_override() -> None:
    """A relative production path should resolve from the project root."""

    result = resolve_database_path("data/demo/rotation_lab.duckdb")

    assert result == (PROJECT_ROOT / "data/demo/rotation_lab.duckdb").resolve()


def test_resolve_database_path_preserves_absolute_override(
    tmp_path: Path,
) -> None:
    """An absolute override should not be relocated."""

    database_path = tmp_path / "rotation_lab.duckdb"

    assert resolve_database_path(str(database_path)) == database_path.resolve()
