# NBA Samples

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

## Repository Structure

```text
.
├── nba_comp_dashboard/
├── nba_team_1page_style_report.ipynb
├── nba_player_similarity_development_report.ipynb
├── team_style_1page_pdf_reports/
├── player_development_reports/
└── Practice/
```

## Purpose

This repo is meant to show basketball analytics work that is both technical and readable: fetching data, cleaning and ranking metrics, building reusable report logic, creating PDFs, and publishing an interactive Streamlit dashboard.
