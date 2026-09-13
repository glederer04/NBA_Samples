# Player analysis and rotation planning roadmap

September 8, 2026. Section 1's time-based on/off analysis is now implemented; see [the release notes](player-impact-release.md) for the delivered scope, validation and limitations. Possession reconstruction and adjusted impact modeling remain future work. Section 2 is now implemented in Lineup Explorer and Game Review/PDF; see [trio release notes and concrete planner next steps](trio-analysis-release.md). Section 3 is now implemented in Scenario Planner; see [player-minute planner release notes](player-minute-planner-release.md) for delivered scope, validation and remaining modeling limitations. Keep the current three-lineup scenario tool available until a player-based replacement has been validated.

## 1. Player on/off analysis

### Where and how to use it

Add a **Player Impact** page between Lineup Explorer and Recommendations, with links from player cards. Start with a player selector, date/season scope, and a clearly labeled game universe: games the player appeared in versus all covered team games. The default should use appearances, so missed games do not silently become the off-court comparison. Show on-court, off-court, and difference side by side, with minutes, possessions, and games for both samples.

In Game Review, add a compact “Player on/off in this game” table below the five-player units. Single-game values describe the game; they should not rank player quality. Clicking a timeline player can eventually open that player's season context.

The questions this answers are: How did the team perform while this player played? What happened during rest minutes? Which teammates were most often on the floor in each group? An on/off difference also reflects teammates, opponents, roles, schedule, and game state; it is not isolated player impact.

### Metrics and data

Initially reuse the scored five-player intervals. Explode each validated interval into five player records, retaining interval identity so points and minutes are aggregated once for each player's on-court sample. Derive off-court totals from the same covered team-game universe minus the on-court totals. Never subtract totals collected under different filters.

With current data, accurately label time-normalized rates:

- On margin per 48 = `48 × (on PF − on PA) / on minutes`.
- Off margin per 48 = `48 × (off PF − off PA) / off minutes`.
- On/off swing = on margin per 48 minus off margin per 48.

Do not call these possession-based net ratings. After implementing and validating possession reconstruction, add offense per 100 offensive possessions, defense per 100 defensive possessions, and their difference. NBA's glossary defines net rating as the difference between offensive and defensive rating: [NBA glossary](https://www.nba.com/stats/help/glossary).

Possession reconstruction must handle offensive rebounds, free-throw sequences, technical free throws, and-ones, jump balls, period ends, corrections, and substitutions inside possessions. Document the allocation rule for split possessions; reconcile period/game possessions and score totals. Avoid the box-score `0.44 × FTA` approximation for precise stint attribution.

### Implementation and validation

1. Add normalized interval membership and player-on/off marts without changing existing scoring views.
2. Preserve boundary-point flags, coverage, date range, and game count in every result.
3. Validate `on minutes + off minutes = covered team minutes`, and corresponding PF/PA totals. Assert exactly five memberships per eligible interval.
4. Show separate uncertainty for both on/off groups; require enough exposure on both sides. Bootstrap entire games rather than treating dependent possessions as independent observations.
5. Add exclusions for low-quality intervals; make garbage-time filtering an explicit later feature with published rules, not an invisible adjustment.
6. Consider regularized adjusted plus-minus only after adding opponent lineups and sufficient data. Fit chronologically and report out-of-sample error; do not label raw on/off causal impact. A methodological reference is [On Estimating the Ability of NBA Players](https://arxiv.org/abs/1008.0705).

### Visual design

Use a small aligned on/off comparison chart with a zero-centered swing indicator, generous numeric labels, and a sample line beneath. Keep detailed splits in a table. Offer teammate overlap and opponent context through expandable detail, avoiding another crowded set of cards.

## 2. Three-player combinations

### Where and how to use it

Extend Lineup Explorer with a **Unit size: Five players / Three players** switch. A trio is three teammates simultaneously on court, with the other two spots allowed to vary. Coaches can identify a useful core and examine which two players completed it successfully.

Selecting a trio should show its usage, PF/PA, raw margin per 48, sample-adjusted result, games, uncertainty, and boundary points. Below it, show the actual five-player completions and their separate samples. Add include/exclude player filters and links into the future planner.

### Correct aggregation

Each five-player interval contributes to its `C(5,3) = 10` trios. Use sorted player IDs as stable trio keys and deduplicate each `(game, interval, trio)` record before aggregation. Within a trio, sum underlying points and exposure, then calculate rates; do not average the five-player lineup rates.

The ten trio records overlap. Summing all trio minutes produces ten times team minutes, and cannot be presented as independent team exposure. Similarly, do not add several trio estimates together to predict a five-player lineup: the same players and observations are shared.

Use a separate shrinkage model or prior for trios, calibrated on held-out games. Display minimum minutes and games and uncertainty. Larger aggregate trio samples do not prove that every five-player completion works equally well.

### Steps

Build a materialized trio membership/aggregation table during ingestion, index or cluster its team/game keys, and cache filtered reads. Test ten unique trios per valid five-player interval; verify trio totals against direct interval membership filters. Add completion drill-down before adding trio “recommendations,” so the source of any apparent advantage remains visible.

## 3. Player-based Scenario Planner

### Intended coaching workflow

1. Select team, active roster, and game context. Availability should come from an explicit roster selection; historical sample players must not automatically be assumed available today.
2. For each player, set minimum and maximum minutes using paired number inputs and an optional range slider. Examples: 15–20, 10–15, and 40–48 minutes. Give starters, closers, rest windows, and maximum stint length separate controls.
3. Add a small number of basketball constraints: at least one primary handler, a designated interior defender, staggered creators, or particular pairs to keep together/apart. Let the user define roles rather than inferring them from a rigid position label.
4. Validate feasibility immediately. Regulation requires exactly **240 player-minutes** and five players on court throughout. Therefore `sum(minimums) ≤ 240 ≤ sum(maximums)` is necessary but not sufficient. Locked windows, role coverage, and rest requirements can still conflict.
5. Press **Build rotation**. Return a feasible rotation with a projected range, evidence coverage, and an explanation of constraints and tradeoffs. Offer a few materially different feasible alternatives rather than claiming one universally optimal rotation.
6. Let a coach lock a stint or change a range, then re-optimize the remaining schedule. Preserve manual edits and display which constraints are binding.

### Optimization model

Start with 30- or 60-second slots; use 48 minutes for regulation, and treat overtime as an explicit later scenario. A 30-second grid yields 96 slots. Explain that planned substitutions occur on this grid; live substitutions still depend on stoppages.

Let `z[l,t]` be binary: lineup `l` is on court in slot `t`. For slot duration `Δ` minutes:

- One lineup per slot: `sum_l z[l,t] = 1`.
- Player minutes: `L[p] ≤ Δ × sum_t sum_(l contains p) z[l,t] ≤ U[p]`.
- Exclude unavailable players and illegal lineups from the candidate set.
- Encode starters/closers and locked windows as fixed decisions.
- Add maximum continuous stint and minimum rest constraints on player presence `x[p,t] = sum_(l contains p) z[l,t]`.
- Penalize substitutions using transition variables bounding `|x[p,t] − x[p,t−1]|`; account for quarter breaks when modeling fatigue and rest.

A useful initial objective is expected score margin minus explicit penalties for uncertainty, excessive changes, and departing from coach preferences:

`maximize Σ(t,l) Δ/48 × μ[l] × z[l,t] − λ_uncertainty × risk − λ_changes × transitions − λ_preference × deviations`.

Here `μ[l]` is a margin-per-48 estimate. This time-normalized objective can be used before possession modeling. After possession reconstruction, use expected possessions times net points per possession instead, keeping units consistent. Do not mix a per-100-possession estimate with minute weights without a pace assumption.

Use hard constraints for availability and safety-related coaching restrictions; softer preferences may have explicit penalties. Never silently relax a hard minute range. If infeasible, identify the conflicting ranges/windows and propose changes for the coach to accept. A mixed-integer solver is suitable; [SciPy MILP documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) and [LinearConstraint documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.LinearConstraint.html) describe the supported objective and bounded linear constraints. Prototype with sparse constraints, a fixed time limit, and report solver status and optimality gap.

### Estimation and new metrics

The existing three-lineup tool uses observed five-player samples. A player-based optimizer needs estimates for many unseen combinations, otherwise it cannot satisfy reasonable minute ranges.

Build an initial regularized model using player presence and team/opponent context; optionally include strongly regularized pair/trio effects only where data support them. Use opponent lineups, home court, period/game state, and chronological train/test splits. Prevent leakage from later games. Compare against simple team-baseline and current-shrinkage baselines before presenting an improvement.

For observed lineups, blend observed performance with model estimates using exposure-based shrinkage. For unseen lineups, display “model-based / no direct sample.” Do not sum raw player on/off swings or overlapping trio rates to estimate a lineup.

Report:

- Planned minutes and range compliance for each player.
- Projected margin range under stated pace/opponent assumptions, not a guaranteed score.
- Expected offensive/defensive rates only after those models are validated.
- Direct-sample coverage: share of planned time in observed, sufficiently sampled lineups.
- Uncertainty or scenario spread; game-level bootstrap/refits can preserve lineup covariance.
- Maximum stint, rest intervals, substitutions, creator coverage, and overlap minutes for key pairs.
- Sensitivity: how the schedule and projection change when a player's cap changes or a player is unavailable.

Do not add a fatigue penalty with invented physiology. Start with coach-entered stint/rest limits; add a learned fatigue adjustment only with supporting data and validation. Uncertainty should remain visible because optimization can aggressively exploit noisy estimates.

### Visualization and reports

Reuse the Rotation Timeline design as the centerpiece: player rows, quarter markers, planned stints, and a thin lineup band showing the active five-player unit. Add a compact per-player target/actual minute table alongside or beneath it. Use a color-mode control: player identity, projected unit performance, or evidence quality. Do not use historical stint +/- colors for a forecast without explicitly labeling it projected.

Hover should reveal five players, duration, expected rate, uncertainty, direct sample, and constraint notes. A details drawer can show the evidence for one stint. Drag-to-edit can come later; first ship accessible inputs and lock/unlock controls that work on phones and keyboards.

A PDF should contain one-page coaching schedule, minute targets versus assigned minutes, starters/closers, and assumptions; append lineup evidence and alternatives. Export the exact saved plan, not an asynchronously recomputed version.

### Delivery sequence and acceptance criteria

1. Data quality, roster/availability inputs, and feasibility checker.
2. Player minute-range editor and a feasible schedule generator using conservative existing estimates.
3. Schedule visualization, manual locks, persistence, and PDF export.
4. Opponent-aware model and uncertainty, validated chronologically.
5. Alternative plans, sensitivity, live adjustments, and optional drag editing.

Test exact five-player coverage, minute bounds, no unavailable players, valid rest/stint windows, and correct treatment of quarter breaks and overtime. Compare optimizer output with hand-built cases. Test infeasible inputs, timeouts, and interrupted requests. Version constraints, model, dataset, and resulting plan so every exported recommendation can be reproduced.
