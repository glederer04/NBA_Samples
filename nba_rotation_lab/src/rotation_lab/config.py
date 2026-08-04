"""Central filesystem and project configuration."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "db"
DEMO_DATABASE_DIR = DATA_DIR / "demo"

SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "reports"
GENERATED_REPORTS_DIR = REPORTS_DIR / "generated"
ASSETS_DIR = PROJECT_ROOT / "assets"

DEFAULT_DATABASE_PATH = DATABASE_DIR / "rotation_lab.duckdb"
DEMO_DATABASE_PATH = DEMO_DATABASE_DIR / "rotation_lab.duckdb"


def resolve_database_path(
    configured_path: str | None = None,
) -> Path:
    """Resolve an override from the process working directory."""

    path_value = configured_path

    if path_value is None:
        path_value = os.getenv("ROTATION_LAB_DATABASE_PATH")

    if path_value is None or not path_value.strip():
        return DEFAULT_DATABASE_PATH

    database_path = Path(path_value).expanduser()

    if not database_path.is_absolute():
        database_path = Path.cwd() / database_path

    return database_path.resolve()


DATABASE_PATH = resolve_database_path()


def ensure_project_directories() -> None:
    """Create runtime directories that may not exist in a fresh checkout."""

    directories = [
        RAW_DATA_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
        DATABASE_DIR,
        DEMO_DATABASE_DIR,
        GENERATED_REPORTS_DIR,
        ASSETS_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
