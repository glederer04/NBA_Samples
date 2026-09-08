# Team logo assets

Official NBA team logo SVGs downloaded on September 7, 2026 from:

`https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg`

Team IDs/abbreviations came from the project's existing `nba_api.stats.static.teams` reference. The SVGs are stored unchanged. PNGs are derived 200-pixel transparent raster versions for ReportLab, with the SVG class styles expanded before rendering to preserve team colors. No network requests are needed to use these assets in the app or generated reports.

NBA team names and logos belong to their respective rights holders. These files support the existing independent analytics portfolio project and do not imply endorsement.

The `normalized/` PNGs are used in the dashboard and PDF header. Run `python scripts/normalize_team_logos.py` (requires Pillow) to regenerate them from the original PNGs. Artwork is cropped to its alpha bounds, scaled proportionally to a 160-pixel maximum dimension, and centered on a transparent 192×192 canvas.
