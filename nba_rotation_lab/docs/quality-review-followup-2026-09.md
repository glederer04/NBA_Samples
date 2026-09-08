# Rotation Lab follow-up review — September 7, 2026

This pass addresses the follow-up requests after the initial quality review. Changes are limited to NBA Rotation Lab. Basketball queries, scoring assignments, shrinkage, confidence, recommendation rules, and scenario formulas are unchanged.

## Important changes

- **Team logos:** all 30 bundled logos now use transparent 192×192 canvases with centered artwork sized to a 160-pixel maximum dimension. This removes inconsistent source padding while preserving aspect ratios and team colors. Dropdown selections, menus, opponent rows, and PDF branding use these normalized assets. A local placeholder handles unavailable images. The normalization script makes this reproducible.
- **PDF downloads:** browser-native attachment endpoints replace the dashboard's base64/blob download callbacks. Both report controls now offer Download PDF and Preview PDF. Exports reflect the current selection, validate incoming plans, and show readable errors without exposing internal exceptions. Generated PDFs are cached with database-change invalidation, eliminating repeated generation for identical requests.
- **Complete Lineup Table:** a light filter row, white input fields, clear placeholders, and explanatory text distinguish filters from results. Numeric columns hide irrelevant case-sensitivity buttons. A discovered Dash behavior required explicit case-sensitive numeric filters: case-insensitive comparisons treated values lexically. The corrected `Games > 20` filter returns only the 43-game lineup in the NYK sample.
- **Shorter names:** table rows use first initial plus surname, preserving suffixes and short uppercase names such as OG. Full names remain in hover tooltips and player cards; abbreviation collisions within a lineup use full names.
- **Navigation:** Rotation Timeline now follows Game Review and precedes Recommendations.

## Verification

- Revisited all six pages locally and visually checked the affected controls, dropdown logos, table header/filter row, navigation, and report controls.
- Chrome emitted download events for both game and scenario links. The in-app browser did not expose a saved download, so use Chrome for the verified download flow. Preview is separately available.
- Flask integration tests verify attachment/inline headers, PDF content type and length, valid PDF parsing, current-plan content, invalid selections, nonfinite minutes, unavailable games, and readable generation failures.
- Rendered and inspected every page of sample game (3 pages) and scenario (2 pages) PDFs. Full lineup names and methodology remain in reports; long game detail continues onto additional pages.
- Local test-client timings: game report 66.66 ms on first request, 0.26 ms cached; scenario 206.96 ms first request, 0.25 ms cached. Files were 39,097 and 37,101 bytes. These are local server timings, not browser/network latency guarantees.
- Full test suite and Ruff checks pass. No basketball calculation modules or SQL were modified.

## Useful next improvements

1. Add persistent team/game selection across Game Review and Rotation Timeline, with direct links between matching games.
2. Consider a column chooser and sticky lineup column for the wide results table, particularly on phones. Preserve access to all existing metrics.
3. Add repeatable browser regression coverage for downloads, native numeric filters, dropdown images, and small-screen layouts.
4. Cache player headshots locally with explicit refresh behavior; team logos already work without external requests, while headshots still depend on the existing remote source and fallback.
5. For a multi-worker deployment, consider a shared bounded cache and production request timing instrumentation. Current PDF/query caches are process-local.
6. Consider report options for a compact executive brief versus the full rotation detail. The current game report deliberately retains all qualifying stretches.
