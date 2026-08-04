"""Initialize the NBA Rotation Lab DuckDB database."""

from rotation_lab.config import DATABASE_PATH
from rotation_lab.database import initialize_database, list_user_schemas


def main() -> None:
    """Initialize the database and print a concise status summary."""

    executed_files = initialize_database()

    print(f"Database initialized: {DATABASE_PATH}")
    print("Executed SQL files:")

    for sql_path in executed_files:
        print(f"  - {sql_path.name}")

    print("Available schemas:")

    for schema_name in list_user_schemas():
        print(f"  - {schema_name}")


if __name__ == "__main__":
    main()
