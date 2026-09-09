# Player Impact: on/off analysis

September 9, 2026

## What changed

- Added **Player Impact** between Lineup Explorer and Recommendations. Game Review and Rotation Timeline remain adjacent.
- Added player, season and date controls. The default universe is games the player appeared in. An explicit alternative includes all covered team games, counting absences as off-court time.
- Added on/off team margin, team points and opponent points per 48 minutes; raw minutes, PF, PA and exposure games; a symmetric zero-centered chart and plain-language interpretation.
- Added a direct two-player comparison using **shared appearance games**, regardless of the single-player universe setting. A portrait card keeps each player's values aligned on their own side, with the metric centered and a gap badge on the favorable side. It covers both on/off change and team performance while on court. Full splits remain expandable. Insufficient samples do not receive an edge badge; intervals crossing zero are marked uncertain. Differences use unrounded rates, so a displayed gap can differ slightly from subtracting rounded values.
- Limited every shared team selector to NYK and SAS, including local databases with additional teams. Player Impact rejects other team requests. Opponent data remains available as game context. Player-card links preserve the source team, including traded players with history on both featured teams.
- Added expandable teammate overlap, opponent splits, coverage information and scoring sensitivity. Teammate rows overlap and must not be summed as independent exposure.
- Added a compact **Player on/off in this game** table below the game lineup cards. Player names link to season context; player names on lineup/recommendation cards also link to Player Impact.

## Calculations and safeguards

Existing lineup scoring views, basketball calculations, recommendations and scenario formulas are unchanged. New views normalize five memberships per scored interval, retain `(game_id, team_id, interval_number)`, and expose player-game on/off totals. The UI loads one row per interval with its membership list and caches the database read with the existing file/WAL fingerprint invalidation.

Every filter is applied before aggregation. Off seconds/PF/PA equal the filtered team totals minus that player's on totals. Rates use unrounded total seconds, not averages of rounded lineup rates. Overtime uses its actual exposure and is still normalized to 48 minutes.

The default quality rule requires five-player coverage across the game, coverage through the last play-by-play time, play-by-play reconciliation and lineup-score reconciliation. Invalid player-count intervals are always omitted. The alternate quality setting includes available valid intervals from partial/flagged games and reports the reduced coverage. Coverage is measured against the scoped games before quality exclusions; date bounds and excluded game counts remain visible.

The boundary sensitivity option removes whole intervals whose existing `boundary_scoring_points` is nonzero from both groups. It preserves the original `(start, end]` scoring convention and does not redistribute points or change the source data. Existing signed scoring corrections are preserved. Garbage time remains included, explicitly.

95% percentile intervals use 2,000 deterministic whole-game bootstrap draws. On/off observations stay paired within each game. Each side needs at least 100 minutes across 10 games for its interval; a swing requires both sides. The two-player swing difference uses the same resampled game indexes for both players. These are transparent display thresholds, not a fitted reliability guarantee. Repeated observations within a game are not treated as independent.

On/off describes **team outcomes in different contexts**, not isolated causal player ability. Teammates, opponents, roles, schedule and game state can explain an apparent difference. Comparing many metrics/players is exploratory; the intervals are pointwise, not adjusted for multiple comparisons.

## Validation and operation

- Automated validation covers all eligible NYK and SAS intervals in a freshly migrated copy of the deployment snapshot: exactly five unique memberships, on/off seconds and PF/PA conservation, and total on-player exposure equal to five times team exposure.
- Synthetic cases cover dates, missed-game universes, shared appearances, quality exclusions, boundary sensitivity, no minutes, no off minutes, overtime, exposure weighting, deterministic resampling and paired comparison covariance.
- App startup transactionally installs only the new view definitions before opening Dash readers. Existing deployment snapshots therefore migrate without a binary database replacement. The SQL is also part of normal database initialization and demo builds.
- Local measured data load was approximately 0.4 seconds per team; cached page calculation approximately 0.07–0.10 seconds, and matched comparison approximately 0.02 seconds. These are local measurements, not hosted latency guarantees.
- All 107 tests pass; Ruff lint and formatting checks pass. Local visual inspection covered all seven tabs, player/team/comparison selection, teammate and opponent details, and boundary sensitivity. At 390px width, the comparison stays side by side without page overflow. An explicit 275px chart container fixes the overlap found during resizing. Player portraits use the existing image fallback.

## Deliberately deferred

Trio analysis and the player-minute planner remain unimplemented. Possession counts, per-100 ratings, adjusted plus-minus and causal claims are also deferred as specified in the roadmap. Possession reconstruction must first reconcile substitutions, free throws, offensive rebounds, corrections and game totals. Adjusted models require opponent lineup data and chronological out-of-sample validation. A published garbage-time rule and clickable timeline-to-player drill-down remain possible follow-ups.
