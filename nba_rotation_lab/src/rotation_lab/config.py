"""Central filesystem and project configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DATABASE_DIR = DATA_DIR / "db"

SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "reports"
GENERATED_REPORTS_DIR = REPORTS_DIR / "generated"
ASSETS_DIR = PROJECT_ROOT / "assets"

DATABASE_PATH = DATABASE_DIR / "rotation_lab.duckdb"


def ensure_project_directories() -> None:
    """Create runtime directories that may not exist in a fresh checkout."""

    directories = [
        RAW_DATA_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
        DATABASE_DIR,
        GENERATED_REPORTS_DIR,
        ASSETS_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
