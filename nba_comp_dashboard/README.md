# NBA Player Comp Dashboard

Live app: https://lederer-nbasamples-player-comp.streamlit.app

This is an interactive Streamlit dashboard where users build a custom basketball profile and get NBA player-season comps.

Users choose a position type, enter skill percentiles, and the app returns:

- Closest NBA player comp
- Radar/spider chart
- Archetype-style role card
- Similar player-season table
- Option to view 5, 10, or 25 comps

The percentiles are meant to be relative to the people a user actually plays with, such as pickup games, school team, rec league, or workout group. They are not meant to be NBA-level self-ratings.

## Project Structure

```text
nba_comp_dashboard/
├── app.py
├── requirements.txt
├── data/
│   ├── README.md
│   └── player_similarity_profiles.csv
└── src/
    ├── __init__.py
    ├── archetypes.py
    ├── charts.py
    ├── data_loader.py
    └── similarity.py
```

## Notes

The app uses a local CSV export instead of calling the NBA API each time it runs. This keeps the dashboard faster and easier to deploy on Streamlit Community Cloud.
