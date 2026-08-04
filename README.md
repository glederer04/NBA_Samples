# NBA Samples

This is an active work in progress, with more reports, tools, and improvements continuing to be added.

This repository is a small NBA analytics portfolio focused on turning basketball data into useful reports, visuals, and interactive tools.

The work here uses Python to pull, clean, analyze, and present NBA data in a way that is readable for scouting, player development, and portfolio review.

## Featured Project

### NBA Rotation Lab

- Live app: https://glederer-nba-rotation-lab.onrender.com
- Code and documentation: [`nba_rotation_lab/`](nba_rotation_lab/)
- Application framework: Dash and Plotly
- Data layer: DuckDB and SQL
- Reporting: Interactive dashboards and downloadable PDF game and scenario reports

NBA Rotation Lab is an end-to-end lineup and rotation decision-support system. It ingests NBA game data, reconstructs five-player lineup intervals, attributes scoring to those units, and presents the results through coach-facing analysis tools.

The application includes:

- Executive team and rotation summaries
- Five-player lineup exploration
- Full-game rotation timelines
- Game review dashboards
- Sample-adjusted lineup recommendations
- Interactive rotation scenario planning
- Downloadable PDF game reports
- Downloadable PDF rotation-scenario reports

The project demonstrates Python application development, relational data modeling, layered SQL transformations, basketball analytics methodology, automated testing, reporting, and communication of findings for coaches and basketball operations staff.

![NBA Rotation Lab executive dashboard](nba_rotation_lab/docs/images/executive-overview.png)

## Live Dashboards

### NBA Player Comp

- Live app: https://lederer-nbasamples-player-comp.streamlit.app
- Code: `nba_comp_dashboard/`

This is my first interactive dashboard/site built with Python and Streamlit.

Users enter their basketball position type and skill percentiles, then the app returns an NBA player-season comparison. It includes a closest comp, radar chart, archetype-style role card, and a table of similar NBA player seasons.

The dashboard builds on the player similarity work from the development report notebook and turns it into a more fun, user-facing experience.

## PDF Report Generators

### Pregame Gameplan Report

- Code: `nba_pregame_gameplan_report.ipynb`
- Sample PDFs: `pregame_gameplan_reports/`

This notebook builds a one-page, landscape pregame gameplan report for a selected team and opponent. It trains a pregame win-probability model using only information available before tipoff, then turns the matchup into coach-facing goals for efficiency, turnovers, rebounding, free throws, 3-point volume, and pace.

The report includes team branding, current records and ranks, matchup-specific goal cards, a clean metric comparison table, and a goal pressure map that compares each team by blended season and recent-form percentile.

### Team Style One-Page Report

- Code: `nba_team_1page_style_report.ipynb`
- Sample PDFs: `team_style_1page_pdf_reports/`

This notebook builds a one-page team style report using NBA team-level data. It pulls team statistics, play type data, shot location profiles, defensive shot data, and hustle metrics, then organizes them into a concise PDF with team colors and summary tables.

### Player Similarity & Development Report

- Code: `nba_player_similarity_development_report.ipynb`
- Sample PDFs: `player_development_reports/`

This notebook creates a one-page player development profile. It compares a selected player-season against similar NBA player-seasons, adds role and archetype context, summarizes strengths and development areas, and includes visual sections such as percentile profiles and shot location information.

## Tools

This repository uses:

- Python
- SQL
- DuckDB
- pandas and NumPy
- Dash and Streamlit
- Plotly and Matplotlib
- nba_api
- ReportLab
- scikit-learn
- pytest and Ruff
- Docker and VS Code Dev Containers
- GitHub Actions

## Repository Structure

```text
.
├── nba_rotation_lab/
├── nba_comp_dashboard/
├── nba_pregame_gameplan_report.ipynb
├── nba_team_1page_style_report.ipynb
├── nba_player_similarity_development_report.ipynb
├── pregame_gameplan_reports/
├── team_style_1page_pdf_reports/
├── player_development_reports/
└── Practice/
```

## Purpose

This repo is meant to show basketball analytics work that is both technical and readable: fetching data, cleaning and ranking metrics, building reusable report logic, creating PDFs, and publishing an interactive Streamlit dashboard.
