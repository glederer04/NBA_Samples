# Portfolio follow-up — September 8, 2026

## Implemented

### Deployment logo fix

Render installs a wheel using `pip install .`. Resource lookup previously walked upward from the installed package, finding the Python environment rather than the application's assets folder. Local editable installs worked, masking the deployment problem. Configuration now discovers the actual application root (or accepts `ROTATION_LAB_PROJECT_ROOT`) and Dash explicitly serves its assets folder. This also fixes PDF logo lookup and other filesystem resources under a wheel installation.

All normalized PNG artwork, aspect ratios, 28-pixel UI boxes, and local fallback behavior remain. The prior commit was already on origin/main; pushing alone would not have solved the package-path problem. The live PNG endpoint itself returned HTTP 200 before the fix, while server-side resource lookup could still choose the placeholder.

### Shared individual-game selection

Game Review and Rotation Timeline now use a common session-scoped team/game selection. Both restore the last selected game when revisited, including after navigating through another page. Changing team validates the game against that team's available games. Explicit Game Review deep links take precedence over remembered selection. Selections are per browser session, not shared across unrelated users.

### Recommendations with an evidence floor

The default page filters the entire recommendation pool to **100+ minutes and 10+ games before taking the top ten**. Developing (30+ minutes / 5+ games) and Exploratory (5+ minutes) views retain access to smaller samples. Units below the default evidence floor are explicitly labeled exploratory in these views, even if their adjusted margin is high.

Ranks are within the selected evidence group. They are not declarations of true lineup quality. The underlying adjusted margin, team baseline, and scenario model are unchanged. The existing `minutes / (minutes + 48)` number is now labeled **sample weight** on this page; it is a shrinkage weight, not a calibrated confidence probability. The 100-minute/10-game floor is an explicit product rule, not a statistical guarantee; future validation should calibrate it.

On the development data, the default Knicks results include 122.61 minutes/16 games, 119.18/20, and 540.57/43. Spurs results include 136.44/19, 284.31/29, 132.84/17, and 115.38/13. A heavily used lineup can still rank below another qualifying lineup if its adjusted margin is lower.

### Rotation map colors

Each player stint now carries the team's score margin over that exact stint, using the existing scoring-event deltas and `(start, end]` timestamp convention. Red indicates negative, neutral gray even, green positive. The scale is symmetric around zero and sized to the current game's largest absolute stint margin (minimum ±5). Color intensity should therefore be compared within one game. Exact margins appear in the hover detail. A short sentence explains the colors without a separate chart legend.

These are team points while the player is on court, not points attributable solely to that player. The chart still uses one Plotly trace to keep rendering efficient.

### Boundary column explanation

Renamed the Lineup Explorer column **Boundary pts** and explained it beside the table. It counts points scored by either team at an exact ending timestamp of a lineup interval. Existing scoring assigns these points to the ending lineup and flags them because substitution ordering at identical timestamps can be ambiguous. It is not possessions, substitutions, fouls, or an error count; it is already included in the displayed scores.

## Proposed work, not implemented

See [Player analysis and planning roadmap](player-analysis-and-planning-roadmap.md) for placement, metrics, data preparation, validation, mathematical formulation, visual design, and implementation stages for on/off analysis, three-player combinations, and a player-minute-range optimizer. The existing Scenario Planner remains functional.

## Verification

- 99 tests passed after the final corrections; Ruff lint and formatting passed. GitHub CI also passed for the deployed code commit `2677855`.
- Added tests for wheel-style asset resolution, actual PNG responses, shared selection restoration/deep links/team changes, evidence filtering before limit, stint color values, and score reconciliation for NYK and SAS.
- Built a wheel and loaded it from a separate installation directory with the demo database, matching Render's installation style; NYK resolves to the normalized image and returns HTTP 200.
- Stint margins sum to five times the team-game margin in both tested games, reflecting five players on court.
- Refreshed and visually checked the deployed site in native Safari: NYK/SAS logos render in selectors and menus, recommendation views show established samples, and stint colors display correctly.
- The Safari interaction check exposed a page-mount reset missed by the first unit tests. Each game-page instance now has an identifier, allowing the shared selection callback to distinguish new page mounts from user changes. Verified April 10 transfers from Game Review to Rotation Timeline, then April 9 transfers back, on the deployed site.
- Corrected a Safari sidebar highlight that stayed on the previous route; active navigation now follows the Dash pathname explicitly. Verified live.
- Revisited all six pages locally. Confirmed persistence through an unrelated page and browser refresh in the in-app browser. Checked a 390-pixel phone viewport: no document-wide horizontal overflow, with the rotation map and labels contained in their panel.
- Standard bundled PNGs eliminate the deployment lookup failure without browser-specific logo code. Native Safari and the in-app browser were exercised in this pass; exhaustive coverage of every browser/device is not claimed.

## Additional UI improvement to consider

Use loading placeholders for first-load charts and metrics so Render/network delays do not briefly expose empty Plotly axes. Keep the current data visible during filter updates where appropriate. This is separate from the corrected selection and scoring behavior.
