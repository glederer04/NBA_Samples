# Three-player analysis and complete Game Review exports

September 9, 2026

## What changed

Lineup Explorer now switches between five-player lineups and three-player cores. Only Knicks and Spurs players are analyzed. A core means three players shared the floor; its other two teammates can vary.

The default requires 100 minutes across 10 games. Required and excluded players apply to membership in the core, not to its two additional teammates. Optional dates scope both the analysis and its calibration. The selector includes every matching core, ordered by time together.

The comparison view answers **how the most-used cores performed, and how much evidence supports those results**. Each row identifies all three players, minutes, games, raw team margin per 48, and a whole-game uncertainty range on one shared scale. It replaces the initial, redundant usage-bar design. A dynamic note explains when all displayed ranges overlap. One consistent dot color represents the same measure everywhere; color does not imply a ranking or a selected winner. Compact name chips and responsive rows keep names distinct.

The selected core shows portraits, covered-team-time share, games, scoring totals, raw and sample-adjusted margin, and uncertainty. Its completion table answers a different question: **which two teammates filled the remaining spots?** The six most-used completions appear first; the remainder can be expanded. Each completion retains its own minutes, games, share, PF/PA, margin and exposure label. A well-established trio does not validate a rarely used five-player completion.

Game Review and its PDF now use one shared, cached player/core context dataset. Both include player on/off, ordered by minutes played, and only the game's three most-used trios with their most-used completions. The PDF has a dedicated Player & Core Context section with readable tables, definitions and coverage. Existing game/rotation detail is preserved. Season-trio links retain the selected team. The export helper text now names the added content.

Trio content is deliberately concentrated in Lineup Explorer and Game Review. Recommendations continue to evaluate actual five-player units. Scenario Planner remains unchanged until its player-minute replacement is validated. There is no arbitrary trio leaderboard on every page, no overlapping trio contribution added to projections, and no planner link that pretends the current three-lineup tool can accept a trio.

## Aggregation, uncertainty and model validation

- Every valid scored five-player interval contributes to exactly `C(5,3) = 10` sorted, unique memberships. Materialized membership and team/game/core aggregates use primary keys. Only NYK/SAS are materialized.
- Raw seconds and scored points are summed before rates are calculated. Margin per 48 is `2,880 × (PF − PA) / seconds`. No rounded-minute aggregation or average of rates is used. These are time-based team results, not possession ratings or isolated player effects.
- Across all trios, minutes and points total ten times the team totals because groups overlap. They must never be added together to predict a lineup's output. Within one trio, its distinct five-player completions reconcile to 100% of its time and all its points.
- Only fully validated games enter the analysis. Existing end-inclusive scoring and all underlying five-player basketball calculations are unchanged. Scoring-boundary coverage remains available in the method disclosure.
- Raw uncertainty resamples 2,000 whole appearance games with a fixed seed. It is shown only at 100 minutes and 10 games. Ranges describe sampling variation; they are neither simultaneous comparisons nor causal or adjusted-model prediction intervals.
- The trio adjustment has its own calibration: first chronological 50% of covered games train rates, next 25% select the prior weight, final 25% audit untouched outcomes. Candidate weights are 0, 24, 48, 100, 200, 400 and 800 prior minutes. Matched cores require 25 minutes/5 games in the earlier split and 10 minutes/3 games in the later split. At least 40 games and 10 repeated cores in each validation/test split are required. Otherwise the adjusted estimate is unavailable.
- Adjustment is `(minutes × raw + prior_minutes × team_baseline) / (minutes + prior_minutes)`. Time-weighted held-out RMSE compares raw trio rates, the team-only baseline and the adjustment. The final descriptive estimate uses all filtered games after this audit; all split dates and errors are disclosed.

For the current full sample, Knicks calibration chose 48 prior minutes: held-out error was 18.35 raw, 12.44 team-only and 14.61 adjusted. The team-only baseline performed better, so the main view visibly labels the adjustment exploratory. Spurs calibration chose 100 prior minutes: 16.12 raw, 16.78 team-only and 14.66 adjusted. Results are not tuned to player reputation; teammates, opponents, roles and schedule remain confounders. The holdout is one diagnostic on overlapping observations, not universal validation.

## Performance and maintenance

The materialized trio tables refresh atomically after tracked rotation/play-by-play/game ingestion, during demo snapshot creation, and at application startup so older snapshots are migrated. Run `python scripts/refresh_trios.py` after direct database changes that bypass tracked ingestion. Rebuilding both teams takes about 0.3–0.5 seconds on this development machine. No all-30-team trio expansion or per-selection SQL self-join is needed.

Season analysis, game context and PDF bytes use database-fingerprint caching. Changing the detail selector does not rebuild the comparison rows. Hidden five-player and trio modes avoid running each other's expensive rendering work. Exports preserve native HTTP PDF responses and cached repeat downloads.

## Validation

Tests cover ten memberships per interval, aggregate conservation, stable keys, repeat refresh, completion conservation, required/excluded/date filters, empty scopes, deterministic whole-game intervals, holdout isolation, both teams' game context, and real PDF content. Perturbing only test outcomes changes reported test error but cannot choose a different prior weight. The full existing suite remains part of release validation.

Both four-page example Game Review PDFs were rendered and visually inspected page by page. The appended section fits cleanly without clipped names or orphan headings. The final suite passes 116 tests, Ruff lint and formatting. All seven pages were inspected locally, including the existing five-player explorer and Scenario Planner. The redesigned trio rows were checked at desktop and 390-pixel phone widths, with matching names, no page overflow, exclusion filters and an empty-result state. Chrome showed the final aligned evidence rows with no console errors. Native Safari also displayed the final six-row comparison, shared axis, selector and player portraits cleanly, and opened the four-page Game Review PDF with player/core content. Startup against a temporary copy of the older deployment snapshot passed without a full database rebuild, including enriched PDF generation.

Measured locally: cold season analysis took 0.44–0.45 seconds per team and cached reads about 0.2 ms. First game PDF HTTP requests took 0.65 seconds for NYK and 0.09 seconds for SAS; cached repeats took 2 ms. These are development-machine measurements, not hosting guarantees. The PDFs were 31–43 KB. Player comparison group headers now retain both player names while scrolling, so lower metric rows stay attributable.

## Next: player-minute Scenario Planner

The next implementation should start with availability and custom minimum/target/maximum minutes for each player, not three preselected lineups. Keep the existing planner available until the new path passes validation.

1. **Define the plan contract.** Restrict the roster to the selected Knicks/Spurs snapshot. Store availability, per-player min/target/max, optional opening/closing locks, maximum continuous stint, minimum rest and coach-entered role coverage. Validate `0 ≤ min ≤ target ≤ max ≤ 48`, at least five available players and `sum(min) ≤ 240 ≤ sum(max)`. These necessary checks are not sufficient for a feasible timed plan. Use a separate explicit overtime horizon if added later.
2. **Build the candidate five-player pool.** Start from observed eligible lineups with unavailable players removed. Trio completions can identify familiar candidate units, but do not add overlapping trio rates or raw on/off swings into a five-player estimate. If observed units cannot satisfy player ranges, explain the conflict and offer explicitly labeled unobserved combinations. Never silently relax availability or minute bounds. Add a route from a trio completion only once the planner can prefill an actual five-player candidate.
3. **Solve minutes, then schedule.** Use a bounded mixed-integer model on, for example, 30-second slots. Let `x[l,t]` select lineup `l` in slot `t`; require exactly one lineup per slot and five distinct available players. For every player, `min[p] ≤ 0.5 × sum(x[l,t] for l containing p) ≤ max[p]`. Add stint/rest and opening/closing constraints. Penalize target deviations, excessive substitutions and low-evidence units. Expose time limits, feasible-but-not-proven-optimal results, and actionable infeasibility explanations.
4. **Validate the objective before calling it predictive.** Begin with a clearly labeled historical, sample-adjusted five-player comparison. Chronologically validate any new lineup/context model against team-only and existing lineup baselines. Player role fit should be observed or coach-specified; do not infer a player's causal value from raw on/off. Possession-based offense/defense requires separately validated possession reconstruction. Injury, opponent and fatigue effects require real data and out-of-sample evidence, not invented coefficients.
5. **Show what a coach can act on.** A player timeline answers when each player plays/rests; a minutes-range table shows planned minutes against allowed bounds; a compact lineup schedule shows who shares the floor; exposure flags identify speculative units. Compare only meaningful alternatives such as baseline versus proposed plan, with delta and assumptions. Selecting a stint reveals its five-player evidence. Use the same plan object for screen and PDF so constraints, schedule, achieved minutes, assumptions and limitations agree.
6. **Acceptance gates.** Test 240 player-minutes, exactly five eligible players at every slot, all minute/availability/rest/lock constraints, roster edge cases, contradictory ranges, solver timeout, repeatability and export parity. Backtest on held-out games and inspect Knicks/Spurs desktop and mobile screens in Safari and Chrome. Set a measured response-time budget before broadening the candidate pool; cache roster/pool/model inputs, not mutable user edits. Ship the validated minute/schedule workflow before adding opponent or fatigue forecasts.

The detailed mathematical roadmap remains in [section 3](player-analysis-and-planning-roadmap.md#3-player-based-scenario-planner).
