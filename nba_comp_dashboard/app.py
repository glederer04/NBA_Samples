from __future__ import annotations

import streamlit as st

from src.archetypes import build_archetype_summary
from src.charts import build_radar_chart
from src.data_loader import load_player_profiles
from src.similarity import SIMILARITY_COLUMNS, find_similar_players


DEFAULT_PERCENTILES = {
    "SCORING_PCTL": 50,
    "SHOOTING_PCTL": 50,
    "PLAYMAKING_PCTL": 50,
    "REBOUNDING_PCTL": 50,
    "DEFENSE_PCTL": 50,
    "EFFICIENCY_PCTL": 50,
    "RIM_PRESSURE_PCTL": 50,
    "CREATION_PCTL": 50,
}


SLIDER_LABELS = {
    "SCORING_PCTL": "Scoring",
    "SHOOTING_PCTL": "Shooting",
    "PLAYMAKING_PCTL": "Playmaking",
    "REBOUNDING_PCTL": "Rebounding",
    "DEFENSE_PCTL": "Defense",
    "EFFICIENCY_PCTL": "Efficiency",
    "RIM_PRESSURE_PCTL": "Rim Pressure",
    "CREATION_PCTL": "Creation",
}


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="NBA Player Comp Dashboard",
        page_icon="🏀",
        layout="wide",
    )

    st.title("NBA Player Comp Dashboard")
    st.caption("Build a player profile and find your NBA comp.")

    with st.sidebar:
        st.header("Your Build")

        position = st.selectbox(
            "Position",
            ["PG", "SG", "SF", "PF", "C"],
        )

        percentiles = {}

        for column in SIMILARITY_COLUMNS:
            percentiles[column] = st.slider(
                SLIDER_LABELS[column],
                min_value=0,
                max_value=100,
                value=DEFAULT_PERCENTILES[column],
                step=1,
            )

    archetype_summary = build_archetype_summary(position, percentiles)

    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("Archetype")
        st.metric("Build Type", archetype_summary["archetype"])
        st.write("Strengths:", ", ".join(archetype_summary["strengths"]))
        st.write(
            "Development Areas:",
            ", ".join(archetype_summary["development_areas"]),
        )

    with right_col:
        st.subheader("Radar Chart")
        radar_fig = build_radar_chart(percentiles)
        st.plotly_chart(radar_fig, use_container_width=True)

    st.divider()

    st.subheader("NBA Comps")

    try:
        player_df = load_player_profiles()
        comps_df = find_similar_players(player_df, position, percentiles)
        st.dataframe(comps_df, use_container_width=True)
    except FileNotFoundError:
        st.info(
            "Player comp data has not been exported yet. "
            "Next step: create data/player_similarity_profiles.csv."
        )


if __name__ == "__main__":
    main()