# NBA Player Comp Dashboard

Interactive Streamlit dashboard that lets users build a custom basketball player profile and find similar NBA player-season comps.

Users will enter their position and skill percentiles, then the app will return a closest NBA comparison, a radar chart, an archetype-style player card, and a small table of similar player seasons.

## App Concept

The dashboard turns the player similarity logic from the main notebook into a fun user-facing experience.

A user can answer:

- What position do I play?
- How strong am I as a scorer, shooter, passer, rebounder, defender, and finisher?
- Which NBA player-season does my profile most closely resemble?

The app will then show:

- Top NBA player comp
- Top 5-10 similar player seasons
- Radar/spider chart of the user profile
- 2K-style archetype card
- Short strengths and development areas summary

## Planned Structure

```text
nba_comp_dashboard/
├── app.py
├── README.md
├── requirements.txt
├── data/
│   ├── README.md
│   └── player_similarity_profiles.csv
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── similarity.py
│   ├── archetypes.py
│   └── charts.py
└── assets/
    └── dashboard_preview.png