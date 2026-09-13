# Player-minute planner release

September 13, 2026. Scenario Planner now opens in **Player-minute planner** mode. **Lineup allocation (original)** preserves the previous three-lineup workflow and its report.

## Coaching workflow

1. Choose the Knicks or Spurs. The roster comes from the latest season in the selected team's validated historical sample. No player is automatically declared available. Select 5–12 players or explicitly use the ten most-used players as an editable starting point.
2. Edit minimum, target and maximum minutes. Targets are soft preferences; the other limits are hard. Also set maximum stint length and minimum rest. Inputs use whole minutes.
3. Optionally lock opening/closing players, define handlers/interior defenders/creators and require their coverage. Pair rules mean **together** (both play or both rest), **apart** (never together), or **stagger** (at least one plays). Add elapsed-minute rest windows where needed.
4. Build the full 48-minute rotation. The planner checks five eligible players in every minute and exactly 240 player-minutes, plus all ranges, roles, pair rules, opening/closing selections, rest windows and lineup locks. It never silently widens a range or removes a restriction.
5. Inspect a stint using the timeline or the accessible selector. Lock it and rebuild; remove its row under the advanced constraints to unlock it. The compliance table identifies players at their minute minimum or maximum.
6. Build a different rotation under the same constraints, or use the cap/unavailable controls for a sensitivity scenario. Applying a lower cap explicitly lowers that player's minimum and target to fit the cap. Press Build to apply the revised inputs. Comparisons identify the two saved versions and show estimate, established usage, substitution and (for changed inputs) player-minute differences.
7. The latest three plans and their constraints remain in this browser. Restore a saved plan's settings before editing it. A visible notice distinguishes edited inputs from the saved schedule. Refreshing does not silently rebuild a plan. The PDF exports the selected saved snapshot, including its comparison with the preceding plan when present.

Trio completion rows now link **Plan with this five** to prefill an actual five-player unit. Add the bench and set minute ranges before building. A trio itself is never treated as a complete lineup.

## Read the results

- **Estimated margin / 48** is a time-weighted historical comparison of the actual five-player units in the plan. Higher means a larger estimated scoring advantage. It is not a final-score prediction or an individual player ranking.
- **95% estimate range** describes uncertainty in the historical estimate. It does not describe the distribution of future game scores, and it does not correct for every bias introduced by optimizing the same historical sample.
- **Established lineup share** is planned time in units with at least 100 direct minutes and ten games. Observed share also includes smaller samples. Less than one minute is displayed as `<1`, not rounded into a misleading zero.
- **Player entries** counts players entering after tip-off, including changes between quarters. Lower means fewer substitutions; it does not automatically mean a better basketball rotation.
- The timeline has one row per player and a thin lineup band. Identity colors identify the player. Evidence colors distinguish established, smaller and absent direct samples. Estimate colors describe projected unit margin, never actual stint +/−.
- Small-sample estimates remain uncertain. A high estimated margin does not override role choices, availability, matchup knowledge or evidence quality. There is no claim that the optimizer has discovered a universally best rotation.

## Scheduling and limits

SciPy/HiGHS solves a sparse mixed-integer model with 48 one-minute slots. Player-presence variables are binary. Continuous lineup-selection variables are linked to those binary presences, sum to one, and represent five distinct players; therefore different lineups cannot remain fractionally mixed in a valid solution. Minutes and timing are solved jointly, avoiding a separate allocation that may be impossible to schedule.

The objective combines minute-weighted lineup margin, bootstrap uncertainty, player entries and absolute target deviations. Balanced weights are `(1, .35, .18, 1.5)`; fewer-changes weights are `(.5, .5, .75, 2)`; stronger-evidence weights are `(.5, 1, .3, 2)`. Unobserved units receive an additional three-point objective penalty per 48 minutes. These are transparent planning preferences, not learned physiology or probabilities.

The candidate pool contains observed eligible five-player units. Explicit opt-in permits all eligible combinations, at most `C(12,5)=792`. A requested alternative must change at least four of the 48 lineup slots. The solver has a 12-second limit and 2% optimality tolerance. A validated incumbent is returned as **feasible** when the limit expires; it is not called optimal. No incumbent at the time limit is reported as a timeout, not proof of infeasibility. The solver gap belongs to this mathematical objective, not a basketball confidence percentage.

Quarter breaks reset the continuous-stint counter and credit 2, 15 and 2 minutes of rest. Rest spanning a quarter boundary includes that break even when the player exits exactly at the boundary. These explicit planning assumptions are not a fatigue model. Live substitutions require stoppages. Overtime and sub-minute scheduling are not included.

## Estimation and validation

Existing basketball scoring, on/off and trio aggregation are unchanged. The new model uses only the chosen team's latest-season, fully validated intervals. Player presence, opponent identity, home court, period and prior score state enter a duration-weighted ridge model. Full opponent lineups are not available for the complete sample, so no opponent-lineup adjustment is claimed. Planning uses neutral score state and equal quarter weights.

The first 50% of games train the model; the next 25% tune ridge strength from 100, 500, 2,000 and 8,000; the last 25% are untouched later tests. The final observed-lineup blend is tested against both the team mean and the existing 48-minute lineup shrinkage baseline. It is enabled only if it beats both. Refitting to all available games happens after this audit. Player/opponent indicator vocabulary does not use later scoring outcomes.

Current 82-game samples use 41 training, 20 tuning and 21 test games. Weighted interval RMSE (lower is better):

| Team | Context blend | Team mean | Existing lineup shrinkage | Used by planner |
|---|---:|---:|---:|---|
| Knicks | 98.99 | 98.80 | 98.97 | Historical team-prior shrinkage |
| Spurs | 93.25 | 94.13 | 93.92 | Context blend |

For Knicks, opponent/venue controls are disabled with an explanation because those inputs do not change the fallback estimate. The Spurs improvement is modest; it validates the interval estimator against these baselines, not future optimized-game results or causal player effects.

Observed units blend direct margin with 48 prior minutes. Unobserved units have zero direct exposure and use context-only estimates when the context model passes; otherwise they use the team baseline. Raw on/off swings and overlapping trios are never summed into a lineup prediction. There are no unvalidated possession-based offense/defense metrics, invented injury effects or fatigue coefficients.

Two hundred seeded whole-game bootstrap draws refit the model and resample every unit together. Plan uncertainty uses the weighted sum within each common draw, preserving covariance. Adding independent lineup variances would incorrectly ignore that relationship.

## Reports, reliability and performance

A native POST download transports the exact versioned saved plan in a controlled hidden input. The renderer does not query the database or rerun optimization. Reports include a one-page coaching timeline and minute table, the complete five-player stint schedule, lineup samples and estimate ranges, constraints, calibration, solver status and plan/model/dataset identifiers. Comparison information is appended when present. Longer schedules or evidence tables paginate with repeated column headers.

The model and historical inputs are cached with database-file invalidation. Empty roster editors avoid unnecessary model calls. Optimization runs only on explicit button presses, not on every cell edit. A per-process build lock prevents concurrent solves on the single-worker deployment; inputs remain intact when the worker is busy. The UI disables build buttons during a solve. PDF payload size is bounded.

Browser checks found and fixed delayed callback registration, numeric normalization changing saved-plan checksums, an uncontrolled textarea submitting an empty PDF form, a roster initialization race, inherited monospace styling in Safari's editor, and sub-minute samples rounding to zero. Canonical numeric checksums survive browser JSON round trips. The selected schedule stays visible during an interrupted/failed rebuild, and stale-input notices prevent it being mistaken for an updated result.

Local measurements: the two ten-player observed pools contained 160 Knicks and 198 Spurs units. Both produced independently valid rotations within the 12-second solve budget, although optimality was not proven. Initial PDF rendering took approximately 10–15 ms; actual browser downloads were also tested. Runtime and the quality of an incumbent can vary on the hosted free-tier CPU.

## Follow-on work

The original roadmap's core player-minute workflow is implemented. Before extending the modeling claims, prioritize rolling season-by-season validation of optimized plans, a complete opponent-lineup dataset, validated possession reconstruction, and more historical seasons with explicit roster snapshots. Only then consider possession-based offense/defense and learned fatigue effects. Sub-minute scheduling, overtime, drag editing, named cross-device plan libraries and live-game rescheduling are useful later extensions. Keep the current whole-minute lock/editor workflow as the accessible fallback.

## Release checks

137 automated tests pass, with Ruff lint, formatting and whitespace checks clean. The tests include hand-solvable rotations, exact 240-minute coverage, conflicting locks, roles, ranges, quarter-break rest credit, timeouts, invalid incumbents, covariance preservation, chronological tuning isolation, explicit unseen-unit opt-in, canonical saved-plan serialization, and the controlled PDF form.

All seven pages were visually reviewed locally. The planner was exercised through roster selection, saved-plan restoration after refresh, a materially different alternative, stint locking and a Brunson maximum-minute change. Both team reports were rendered and inspected page by page; the complete three-page Safari download was verified on disk. The in-app browser also successfully submitted the selected capped-plan PDF. Existing overview, game review, rotations, lineup explorer, player impact and recommendations retained their layouts and data displays.

Native Safari's timeline, editor and actual PDF download passed. Chrome loaded the Spurs roster and submitted a build, but final native Chrome result/download verification was interrupted by the Mac locking and later the automation connection reporting no available Chrome window. The browser viewport override also failed to change the measured 1280-pixel viewport, so a new phone-width visual pass is not claimed. Responsive styles provide internal scrolling for the timeline/tables and stacked controls; final physical-device verification remains advisable. Dash 4 emits a future-major-version DataTable deprecation warning; a later grid migration should preserve keyboard editing and this constraint contract.
