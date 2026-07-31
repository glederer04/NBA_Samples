# NBA Samples

This is an active work in progress, with more reports, tools, and improvements continuing to be added.

This repository is a small NBA analytics portfolio focused on turning basketball data into useful reports, visuals, and interactive tools.

The work here uses Python to pull, clean, analyze, and present NBA data in a way that is readable for scouting, player development, and portfolio review.

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

This repo uses Python libraries such as:

- `streamlit`
- `pandas`
- `plotly`
- `nba_api`
- `matplotlib`
- `Pillow`
- `scikit-learn`

## Repository Structure

```text
.
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
