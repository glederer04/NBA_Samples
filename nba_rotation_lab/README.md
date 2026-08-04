# NBA Rotation Lab
[![NBA Rotation Lab Quality](https://github.com/glederer04/NBA_Samples/actions/workflows/rotation-lab-quality.yml/badge.svg)](https://github.com/glederer04/NBA_Samples/actions/workflows/rotation-lab-quality.yml)

An end-to-end NBA lineup and rotation decision-support system built with Python, DuckDB, SQL, Dash, Plotly, and ReportLab.

NBA Rotation Lab converts rotation stints, play-by-play events, game results, and player box scores into coach-facing lineup analysis, game reports, sample-adjusted recommendations, and interactive rotation scenarios.

## Project Objective

Basketball operations staff need more than a leaderboard of raw plus-minus results. They need to understand:

- Which five-player units are receiving meaningful minutes?
- Which results are supported by a usable sample?
- When did a game’s strongest and weakest rotation stretches occur?
- How does a proposed rotation plan compare with the team baseline?
- How much confidence should a staff place in each conclusion?

This project demonstrates the complete analytics workflow required to answer those questions:

1. NBA data ingestion
2. Relational data modeling
3. SQL transformation layers
4. Lineup interval reconstruction
5. Sample-size adjustment
6. Interactive decision-support tools
7. Professional PDF reporting
8. Automated testing and validation

## Application Pages

### Executive Overview

Summarizes team record, cumulative margin, lineup usage, rotation changes, data validation, recent games, and most-used units.

![NBA Rotation Lab executive dashboard](docs/images/executive-overview.png)

### Game Review

Provides period scoring margins, game takeaways, best and worst rotation stretches, five-player lineup results, and downloadable PDF reports.

![NBA Rotation Lab game review](docs/images/game-review.png)

### Recommendations

Ranks five-player units using a sample-adjusted estimate rather than raw plus-minus alone.

Recommendation labels include:

- **Prioritize** — adjusted performance meaningfully exceeds the team baseline.
- **Monitor** — results are near the baseline and should remain under evaluation.
- **Limit** — adjusted performance trails the baseline.
- **Exploratory** — the sample is too small for a stronger recommendation.

![NBA Rotation Lab recommendations](docs/images/recommendations.png)

### Scenario Planner

Allows staff to allocate up to 48 planned minutes across selected lineups and compare the resulting scenario with the current team baseline.

Outputs include:

- Planned lineup minutes
- Sample-adjusted scenario margin
- Team baseline
- Projected difference
- Minutes-weighted confidence
- Visual plan comparison
- Staff-facing interpretation
- Downloadable two-page rotation-scenario PDF

![NBA Rotation Lab scenario planner](docs/images/scenario-planner.png)

### Lineup Explorer

Filters five-player units by team, required players, and minimum minutes. Players and lineups are ordered by tracked minutes to keep the most relevant options visible first.

![NBA Rotation Lab lineup explorer](docs/images/lineup-explorer.png)

### Rotation Timeline

Displays player stints, substitution events, lineup changes, and rotation timing for individual games.

![NBA Rotation Lab rotation timeline](docs/images/rotation-timeline.png)

## Technical Architecture

```mermaid
flowchart LR
    A["NBA API data"] --> B["Python ingestion"]
    B --> C["DuckDB raw schema"]
    C --> D["SQL staging views"]
    D --> E["Intermediate lineup intervals"]
    E --> F["Analytics marts"]
    F --> G["Recommendation engine"]
    F --> H["Dash application"]
    G --> H
    F --> I["PDF reporting"]
    G --> J["Scenario modeling"]
    J --> H
    J --> I
```

## SQL Data Model

The database uses layered schemas:

| Layer | Purpose |
|---|---|
| `raw` | Games, teams, players, box scores, rotations, and play-by-play |
| `staging` | Cleaned events and game context |
| `intermediate` | Reconstructed lineup intervals and scoring attribution |
| `marts` | Coverage, rotation profiles, lineup performance, game review, and recommendations |

SQL transformations are stored under `sql/` and executed in dependency order.

## Recommendation Methodology

Raw lineup plus-minus can be misleading when a unit has played only a few minutes.

The recommendation mart shrinks each lineup’s plus-minus per 48 toward its team baseline:

```text
confidence weight = lineup minutes / (lineup minutes + 48)

adjusted +/- 48 =
    confidence weight × raw lineup +/- 48
    + (1 - confidence weight) × team baseline
```

This produces conservative estimates for small samples while allowing established units to retain more of their observed performance.

The recommendations are descriptive decision support. They are not causal estimates and do not account for every contextual variable, including opponent quality, player availability, or matchup assignment.

## Scenario Methodology

The Scenario Planner weights each selected lineup’s adjusted performance by its planned minutes.

```text
scenario +/- 48 =
    sum(adjusted lineup +/- 48 × planned minutes)
    / total planned minutes
```

The scenario is compared with the team baseline over the same planned-minute window.

## Technology Stack

- Python 3.11
- DuckDB
- SQL
- pandas
- NumPy
- nba_api
- Dash
- Plotly
- ReportLab
- pytest
- Ruff
- Docker and VS Code Dev Containers

## Running the Application

From the repository root, enter the Rotation Lab project directory and start Dash:

```bash
cd nba_rotation_lab
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

## Database Initialization

```bash
python scripts/init_database.py
```

The initialization process executes every SQL file under `sql/` in dependency order.

## Generate a PDF Game Report

```bash
python scripts/generate_game_report.py \
    --team NYK \
    --game-id 0022500153
```

Reports are written to:

```text
output/pdf/
```

## Generate a PDF Rotation Scenario Report

Scenario reports can be downloaded directly from the Scenario Planner page. They can also be generated from the command line by supplying a team and one or more lineup allocations:

```bash
python scripts/generate_scenario_report.py \
    --team NYK \
    --allocation 1626157-1628384-1628404-1628969-1628973=24 \
    --allocation 1626157-1628384-1628969-1628973-1629011=24
```

Each allocation uses `LINEUP_KEY=MINUTES` format. The selected units must belong to one team, each unit can appear only once, and total planned minutes cannot exceed 48.

Scenario reports are written to:

```text
output/pdf/
```

## Quality Checks

```bash
python -m ruff format .
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Current project coverage includes 72 automated tests across ingestion, SQL marts, lineup reconstruction, recommendations, reporting, dashboard callbacks, scenario modeling, and production readiness.

## Production Deployment

The repository includes a Render Blueprint at `render.yaml`. The deployed service runs under Gunicorn, checks application and database readiness at `/health`, and uses the tracked read-only demonstration snapshot at `data/demo/rotation_lab.duckdb`.

Local development continues to use the ignored working database at `data/db/rotation_lab.duckdb`. Override the database for any environment with:

```bash
export ROTATION_LAB_DATABASE_PATH=data/demo/rotation_lab.duckdb
```

The Render service is configured to deploy from `main` after GitHub quality checks pass.

## Project Structure

```text
nba_rotation_lab/
├── assets/                 # Dashboard CSS and fallback imagery
├── data/                   # Local DuckDB database and source data
├── pages/                  # Dash application pages
├── reports/                # Report-related project resources
├── scripts/                # Ingestion, inspection, and reporting commands
├── sql/
│   ├── 00_setup/
│   ├── 01_raw/
│   ├── 02_staging/
│   ├── 03_intermediate/
│   └── 04_marts/
├── src/rotation_lab/
│   ├── dashboard/
│   ├── ingest/
│   ├── modeling/
│   ├── recommendations/
│   └── reporting/
└── tests/
```

## Data and Usage Note

NBA Rotation Lab is an independent analytics portfolio project. NBA names and imagery belong to their respective rights holders.

The included data represents a development sample and should not be treated as a complete production dataset or an official team evaluation.

## Potential Extensions

- Opponent-strength and schedule adjustment
- Player-availability scenario controls
- Possession-based lineup efficiency
- Matchup-specific lineup recommendations
- Automated daily data refresh
- Production deployment and authentication
