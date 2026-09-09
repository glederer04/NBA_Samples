-- A stable five-member identity for each scored, valid lineup interval.
CREATE OR REPLACE VIEW intermediate.player_interval_membership AS
SELECT
    game_id, team_id, interval_number,
    CAST(member.player_id AS BIGINT) AS player_id
FROM intermediate.team_lineup_interval_scoring,
UNNEST(STRING_SPLIT(lineup_key, '-')) AS member(player_id);
