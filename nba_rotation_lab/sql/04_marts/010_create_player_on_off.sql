-- Keep the original (start, end] scoring convention and all unrounded exposure.
CREATE OR REPLACE VIEW marts.player_on_off_intervals AS
SELECT scored.*, members.player_id
FROM intermediate.team_lineup_interval_scoring AS scored
JOIN intermediate.player_interval_membership AS members
    USING (game_id, team_id, interval_number);

-- Appearance games only. Other game universes are constructed before aggregation
-- in the dashboard; an absent player is never silently counted as having appeared.
CREATE OR REPLACE VIEW marts.player_on_off_game AS
WITH totals AS (
    SELECT game_id, team_id,
        SUM(duration_seconds) AS covered_seconds,
        SUM(points_for) AS covered_points_for,
        SUM(points_against) AS covered_points_against
    FROM intermediate.team_lineup_interval_scoring
    GROUP BY game_id, team_id
), players AS (
    SELECT game_id, game_date, team_id, team_abbreviation, player_id,
        SUM(duration_seconds) AS on_seconds,
        SUM(points_for) AS on_points_for,
        SUM(points_against) AS on_points_against,
        SUM(boundary_scoring_points) AS on_boundary_points
    FROM marts.player_on_off_intervals
    GROUP BY ALL
)
SELECT players.*, totals.* EXCLUDE (game_id, team_id),
    covered_seconds - on_seconds AS off_seconds,
    covered_points_for - on_points_for AS off_points_for,
    covered_points_against - on_points_against AS off_points_against
FROM players JOIN totals USING (game_id, team_id);
