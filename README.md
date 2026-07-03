# NBA Samples

This repository is a small NBA analytics portfolio meant to demonstrate practical Python coding ability for basketball projects. The work here focuses on pulling NBA data, shaping it into useful scouting context, building repeatable report tools, and producing clean PDF outputs that can be shared or reviewed quickly.

The notebooks are intentionally sample-oriented: they show how raw NBA API data can become team summaries, player development profiles, visual tables, and one-page reports.

## Projects

### Team Style One-Page Report

- Code: `nba_team_1page_style_report.ipynb`
- Sample PDFs: `team_style_1page_pdf_reports/`

This notebook builds a one-page team style report using NBA team-level data. It pulls team statistics, Synergy play type data, shot location profiles, defensive shot data, and hustle metrics, then organizes them into a concise PDF with team colors and summary tables.

The report is designed to give a quick read on a team's strengths, weaknesses, tendencies, and overall playing style.

### Player Similarity & Development Report

- Code: `nba_player_similarity_development_report.ipynb`
- Sample PDFs: `player_development_reports/`

This notebook creates a one-page player development profile. It compares a selected player-season against similar NBA player-seasons, adds role and archetype context, summarizes strengths and development areas, and includes visual sections such as percentile profiles and shot location information.

The goal is to turn player statistics into a more scout-friendly development snapshot.

## Practice

The `Practice/` folder is for exploratory work and skill-building. It currently includes a team profile scouting demo notebook and a sample Celtics snapshot image. These files are separate from the main report tools and are mainly used for experimenting with ideas, visuals, and basketball analytics workflows.

## Tools and Data

The work in this repo uses Python notebooks with libraries such as:

- `nba_api`
- `pandas`
- `numpy`
- `matplotlib`
- `Pillow`

Data is pulled from NBA Stats endpoints through `nba_api`. Generated report examples are included as PDFs so the output of each notebook can be reviewed without rerunning the code.

## Repository Structure

```text
.
├── nba_team_1page_style_report.ipynb
├── nba_player_similarity_development_report.ipynb
├── team_style_1page_pdf_reports/
├── player_development_reports/
└── Practice/
```

## Purpose

This repo is meant to show basketball analytics work that is both technical and readable: fetching data, cleaning and ranking metrics, building reusable report logic, and presenting NBA insights in a polished format.
