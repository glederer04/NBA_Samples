# Rotation Lab quality review — September 2026

## Scope and preserved behavior

This review is limited to `nba_rotation_lab`. All six application pages were run against the existing local DuckDB database and inspected at desktop, tablet (980 px), and mobile (390 px) widths. The project test suite covers ingestion, SQL marts, recommendations, scenario modeling, dashboard data, health checks, and reporting. No ingestion job was run against the user's database.

Basketball formulas, SQL transformations, scoring attribution, recommendation rankings, and scenario projections were not changed. Database caching wraps the existing read functions; it does not rewrite their queries. Existing game links, team/game/player filters, lineup sorting/filtering/pagination, scenario controls, and PDF payload formats remain available.

## Important fixes

| Area | Finding | Change |
| --- | --- | --- |
| Shared layout | Fixed filter widths squeezed page titles and overflowed intermediate screen sizes. Heavy shadows and inconsistent metric grids distracted from the content. | Responsive filter rows, smaller titles, lighter shadows, aligned metric labels, compact mobile navigation, and contained table scrolling. |
| Executive Overview | Dates and scores wrapped; overtime periods displayed as Q5/Q6. | Keep table values on one line within a scroll region; use OT1/OT2 labels. Add opponent logos. |
| Game Review | Percentage graph height could push quarter labels outside the panel. Stretch colors reflected their ranked column rather than their actual sign. | Explicit graph height; positive/negative/zero colors follow the displayed margin. |
| Recommendations | Four metrics occupied a five-column grid. Long player names were truncated. | Four-column desktop/two-column narrow grids and wrapping player names. |
| Scenario Planner | Repeated recommendation queries on minute edits; selected units unreadable when the dropdown truncated names. | Cached reads, 300 ms numeric-input debounce, and complete selected-lineup text below each selector. |
| Lineup Explorer | Rigid player-filter widths and narrow metric cards at tablet sizes. | Flexible filter grids, two-column tablet metrics, more legible mobile lineup statistics, and a 320 px lineup table column with explicit sans-serif typography and contained horizontal scrolling. |
| Rotation Timeline | A separate Plotly trace was constructed for every stint. Empty stints could crash the readout. | One array-backed trace with identical stint positions, colors, and hover data; a readable empty state. |
| PDF downloading | No visible progress, invalid-selection feedback, or recovery message. | Disable the button while generating, show “Preparing PDF…”, announce completion, and surface retry/invalid-selection messages. |
| Game PDFs | Only the first seven qualifying rotation stretches were exported. Tables had inconsistent widths. | Export every stretch returned by the existing game-review query, with repeated table headers across pages; consistent widths. Game PDFs may now exceed two pages. |
| Report design | Two report types used different framing and lacked chart summaries/team branding. | Shared headers/footers, bundled team-logo imagery, and vector charts of existing period/scenario values. |
| Dataset status | Sidebar claimed validation unconditionally. | Label it “Development sample”; page-level validation metrics remain the source of validation status. |
| Accessibility | Several visible filter labels were not associated with their controls. | Add label associations, visible keyboard focus, live export status, and reduced-motion support. |

## Performance measurements

Local median of 12 warm repetitions on the included NYK sample; these are component timings, not a promise of end-to-end page latency:

| Operation | Before | After |
| --- | ---: | ---: |
| Fetch 50 scenario recommendations | 194.93 ms | 0.36 ms (cache hit) |
| Build example rotation chart | 9.80 ms | 5.22 ms |
| Rotation chart traces | 42 | 1 |
| Rotation chart JSON size | 27,632 bytes | 11,603 bytes |

The read cache is per process and bounded to 128 entries per function. Keys include the database path and the database/WAL inode, modification time, and size. File changes invalidate prior results. Returned mutable results are copied so one request cannot corrupt another request's cached data. Cold reads still execute the original queries. Multi-worker deployments have independent caches.

## Verification

- 87 tests passed, including five new regressions for cache copy isolation/invalidation, stint and tooltip preservation, overtime labels, export error feedback, and PDF stretches beyond the old seven-row cutoff.
- Ruff lint passed across the Rotation Lab project.
- All six pages visually inspected at 1280 px desktop, 980 px tablet, and 390 px mobile; no document-level horizontal overflow at tested tablet/mobile widths. Wide data tables intentionally scroll within their panels.
- Scenario validation exercised above 48 minutes, followed by restoration to a valid plan and successful PDF generation.
- Both browser download controls exercised; downloaded files confirmed in the browser's download folder, and PDF structure/text checked.
- Generated PDFs rendered and inspected page by page. The example game report spans three pages; the scenario report remains two pages.
- Major layout, logo/export, and rotation-rendering changes were followed by server restarts and visual verification.

## Local run and checks

From `nba_rotation_lab`, using Python 3.11–3.13:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python app.py
```

Open `http://localhost:8050`. The default database is `data/db/rotation_lab.duckdb`. For a fresh checkout without that local database, use the included deployment sample:

```bash
ROTATION_LAB_DATABASE_PATH=data/demo/rotation_lab.duckdb python app.py
```

Run checks from the project directory:

```bash
python -m pytest
ruff check .
```

This review used an isolated environment in `/tmp/rotation-lab-venv`; no project dependency versions were changed. PyMuPDF was installed only into that temporary environment to render verification PDFs and convert logo assets. It is not an application runtime dependency.

## Assets and remaining limitations

All 30 team logos are bundled as official NBA CDN SVGs, with derived PNGs for offline ReportLab use. See `assets/team-logos/README.md`. Player headshots still use the existing external NBA CDN and retain the local fallback. Bootstrap also remains an external stylesheet; full offline application support was outside this pass.

The existing game-review data query determines which rotation stretches qualify for the report; removing the PDF's seven-row cutoff does not expand or alter those analytical filters. The included sample remains development data, not a production completeness guarantee. Visual checks used the Codex browser; Safari/Firefox and production deployment were not separately verified.
