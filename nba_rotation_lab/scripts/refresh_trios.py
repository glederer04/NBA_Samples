"""Refresh materialized trio evidence after direct raw-data updates."""

from rotation_lab.lineups.trios import refresh_trios

if __name__ == "__main__":
    refresh_trios()
    print("Knicks and Spurs trio evidence refreshed.")
