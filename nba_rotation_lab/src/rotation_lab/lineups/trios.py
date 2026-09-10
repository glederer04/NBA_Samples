"""Materialized, overlapping three-player units; original scoring is unchanged."""

from rotation_lab.config import DATABASE_PATH, SQL_DIR
from rotation_lab.database import connect_database, run_sql_file


def refresh_trios(database_path=DATABASE_PATH):
    """Atomically refresh the two featured teams after ingestion or app startup."""
    with connect_database(database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        run_sql_file(connection, SQL_DIR / "04_marts/011_create_trio_tables.sql")
        connection.execute("""
            CREATE TEMP TABLE trio_scored AS
            SELECT * FROM intermediate.team_lineup_interval_scoring
            WHERE team_abbreviation IN ('NYK', 'SAS')
        """)
        connection.execute("""
            CREATE TEMP TABLE trio_members AS
            SELECT game_id, team_id, interval_number, CAST(p.id AS BIGINT) AS player_id
            FROM trio_scored, UNNEST(STRING_SPLIT(lineup_key, '-')) AS p(id)
        """)
        connection.execute("DELETE FROM intermediate.trio_interval_membership")
        connection.execute("""
            INSERT INTO intermediate.trio_interval_membership
            SELECT a.game_id, a.team_id, a.interval_number,
                CONCAT(a.player_id, '-', b.player_id, '-', c.player_id),
                a.player_id, b.player_id, c.player_id
            FROM trio_members a
            JOIN trio_members b USING (game_id, team_id, interval_number)
            JOIN trio_members c USING (game_id, team_id, interval_number)
            WHERE a.player_id < b.player_id AND b.player_id < c.player_id
        """)
        invalid = connection.execute("""
            SELECT COUNT(*) FROM (
                SELECT s.game_id, s.team_id, s.interval_number
                FROM trio_scored s
                LEFT JOIN intermediate.trio_interval_membership t
                    USING (game_id, team_id, interval_number)
                GROUP BY ALL HAVING COUNT(t.trio_key) != 10
            )
        """).fetchone()[0]
        if invalid:
            raise ValueError(f"Trio refresh aborted: {invalid} intervals did not yield ten cores.")
        connection.execute("DELETE FROM marts.trio_game_performance")
        connection.execute("""
            INSERT INTO marts.trio_game_performance
            SELECT s.game_id, s.team_id, s.team_abbreviation, s.game_date, t.trio_key,
                SUM(s.duration_seconds), SUM(s.points_for), SUM(s.points_against),
                SUM(s.boundary_scoring_points), COUNT(*)
            FROM trio_scored s
            JOIN intermediate.trio_interval_membership t USING (game_id, team_id, interval_number)
            GROUP BY ALL
        """)
        connection.execute("COMMIT")
