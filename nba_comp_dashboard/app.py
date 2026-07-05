from __future__ import annotations

from typing import Dict, List, Union, cast

import pandas as pd
import streamlit as st

from src.archetypes import ArchetypeSummary, build_archetype_summary
from src.charts import build_comparison_radar_chart
from src.data_loader import load_player_profiles
from src.similarity import SIMILARITY_COLUMNS, find_similar_players


PercentileValue = Union[int, float]
PercentileDict = Dict[str, PercentileValue]
TableValue = Union[str, int, float]
CompRecord = Dict[str, TableValue]


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


DISPLAY_COLUMN_NAMES = {
    "SIMILARITY_SCORE": "Similarity",
    "PLAYER_NAME": "Player",
    "SEASON": "Season",
    "TEAM_ABBREVIATION": "Team",
    "POSITION": "Position",
    "PROFILE_GROUP": "Profile",
    "AGE": "Age",
    "PTS": "PTS",
    "REB": "REB",
    "AST": "AST",
    "TS_PCT": "TS%",
    "USG_PCT": "USG%",
    "ARCHETYPE": "Type",
}


def add_page_styles() -> None:
    """Add lightweight custom styling for the app."""
    st.markdown(
        """
        <style>
        .main-result {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            padding: 1.25rem 1.5rem;
            background: linear-gradient(135deg, #111827 0%, #1f2937 55%, #7c2d12 100%);
            color: white;
            margin-bottom: 1rem;
        }

        .main-result-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #cbd5e1;
            margin-bottom: 0.25rem;
        }

        .main-result-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }

        .main-result-subtitle {
            font-size: 1rem;
            color: #e5e7eb;
        }

        .archetype-card {
            border: 1px solid rgba(148, 163, 184, 0.45);
            border-radius: 8px;
            padding: 1.1rem;
            background: #0f172a;
            color: white;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
        }

        .archetype-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(226, 232, 240, 0.18);
            padding-bottom: 0.75rem;
            margin-bottom: 0.9rem;
        }

        .archetype-label {
            font-size: 0.78rem;
            color: #cbd5e1;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .archetype-name {
            font-size: 1.35rem;
            font-weight: 800;
            margin-top: 0.15rem;
        }

        .overall-badge {
            border: 1px solid rgba(250, 204, 21, 0.6);
            color: #fde68a;
            padding: 0.45rem 0.65rem;
            border-radius: 6px;
            font-weight: 800;
            text-align: center;
            min-width: 64px;
        }

        .badge-number {
            font-size: 1.35rem;
            line-height: 1;
        }

        .badge-text {
            font-size: 0.62rem;
            letter-spacing: 0.08em;
        }

        .skill-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.45rem 0;
            border-bottom: 1px solid rgba(226, 232, 240, 0.10);
            font-size: 0.92rem;
        }

        .skill-name {
            color: #dbeafe;
        }

        .skill-value {
            font-weight: 800;
            color: #f8fafc;
        }

        .small-note {
            color: #64748b;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def estimate_overall(percentiles: PercentileDict) -> int:
    """Estimate a fun 2K-style overall from the user's percentile profile."""
    values = [float(value) for value in percentiles.values()]
    return round(sum(values) / len(values))


def render_intro() -> None:
    """Render the short explanation section."""
    st.title("NBA Player Comp Dashboard")
    st.markdown(
        """
        Build a quick player profile, then see which NBA player-seasons your game most closely matches.
        Use the sliders as percentiles relative to the people you actually play with, like your pickup runs,
        rec league, school team, or workout group. Do not rate yourself as if you were already in the NBA.
        """
    )


def render_main_result(
    archetype: str,
    top_comp_name: str,
    top_similarity: float,
) -> None:
    """Render the headline result."""
    st.markdown(
        f"""
        <div class="main-result">
            <div class="main-result-label">Your Build</div>
            <div class="main-result-title">{archetype}</div>
            <div class="main-result-subtitle">
                Closest NBA comp: <strong>{top_comp_name}</strong>
                &nbsp;|&nbsp; Similarity: <strong>{top_similarity:.1f}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_archetype_card(
    position: str,
    archetype_summary: ArchetypeSummary,
    percentiles: PercentileDict,
) -> None:
    """Render a compact 2K-style archetype card."""
    overall = estimate_overall(percentiles)

    skill_rows = "".join(
        f"""
        <div class="skill-row">
            <span class="skill-name">{SLIDER_LABELS[column]}</span>
            <span class="skill-value">{int(percentiles[column])}</span>
        </div>
        """
        for column in SIMILARITY_COLUMNS
    )

    strengths = ", ".join(archetype_summary["strengths"])
    development_areas = ", ".join(archetype_summary["development_areas"])

    st.markdown(
        f"""
        <div class="archetype-card">
            <div class="archetype-header">
                <div>
                    <div class="archetype-label">{position} Build</div>
                    <div class="archetype-name">{archetype_summary["archetype"]}</div>
                </div>
                <div class="overall-badge">
                    <div class="badge-number">{overall}</div>
                    <div class="badge-text">OVR</div>
                </div>
            </div>

            {skill_rows}

            <div style="margin-top: 0.9rem;">
                <div class="archetype-label">Strengths</div>
                <div>{strengths}</div>
            </div>

            <div style="margin-top: 0.75rem;">
                <div class="archetype-label">Development Areas</div>
                <div>{development_areas}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_comp_options(comps_df: pd.DataFrame) -> Dict[str, int]:
    """Build selectbox labels for comp comparison."""
    options: Dict[str, int] = {}

    for index in range(len(comps_df)):
        row = cast(CompRecord, comps_df.iloc[index].to_dict())
        label = (
            f"{str(row['PLAYER_NAME'])} - {str(row['SEASON'])} "
            f"({str(row['TEAM_ABBREVIATION'])}) | "
            f"{float(row['SIMILARITY_SCORE']):.1f}"
        )
        options[label] = index

    return options


def format_comps_table(comps_df: pd.DataFrame) -> pd.DataFrame:
    """Format and reorder the comps table for display."""
    table_columns = [
        "SIMILARITY_SCORE",
        "PLAYER_NAME",
        "SEASON",
        "TEAM_ABBREVIATION",
        "POSITION",
        "AGE",
        "PTS",
        "REB",
        "AST",
        "TS_PCT",
        "USG_PCT",
        "ARCHETYPE",
    ]

    display_df = cast(pd.DataFrame, comps_df.loc[:, table_columns].copy())

    display_df["SIMILARITY_SCORE"] = display_df["SIMILARITY_SCORE"].round(1)
    display_df["AGE"] = display_df["AGE"].round(1)
    display_df["PTS"] = display_df["PTS"].round(1)
    display_df["REB"] = display_df["REB"].round(1)
    display_df["AST"] = display_df["AST"].round(1)
    display_df["TS_PCT"] = display_df["TS_PCT"].round(3)
    display_df["USG_PCT"] = display_df["USG_PCT"].round(3)

    display_df.columns = [
        DISPLAY_COLUMN_NAMES.get(str(column), str(column))
        for column in display_df.columns
    ]

    return display_df


def style_similarity(value: float) -> str:
    """Color similarity scores from red to green."""
    normalized = max(0, min(float(value), 100)) / 100

    red = int(248 - (normalized * 180))
    green = int(113 + (normalized * 80))
    blue = 113

    return (
        f"background-color: rgb({red}, {green}, {blue}); "
        "color: #111827; "
        "font-weight: 800;"
    )


def get_similarity_column_styles(display_df: pd.DataFrame) -> pd.DataFrame:
    """Build a style dataframe that only colors the Similarity column."""
    styles = pd.DataFrame("", index=display_df.index, columns=display_df.columns)

    for index, value in display_df["Similarity"].items():
        styles.loc[index, "Similarity"] = style_similarity(float(value))

    return styles


def get_comp_record(comps_df: pd.DataFrame, row_index: int) -> CompRecord:
    """Return one comp row as a typed dictionary."""
    return cast(CompRecord, comps_df.iloc[row_index].to_dict())


def get_comp_percentiles(comp_record: CompRecord) -> PercentileDict:
    """Pull the radar-chart percentile values from a comp record."""
    return {
        column: float(comp_record[column])
        for column in SIMILARITY_COLUMNS
    }


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="NBA Player Comp Dashboard",
        page_icon=":basketball:",
        layout="wide",
    )

    add_page_styles()
    render_intro()

    with st.sidebar:
        st.header("Your Build")

        position = cast(
            str,
            st.selectbox(
                "Position",
                cast(List[str], ["PG", "SG", "SF", "PF", "C"]),
            ),
        )

        top_n = cast(
            int,
            st.radio(
                "Number of comps",
                cast(List[int], [5, 10, 25]),
                horizontal=True,
            ),
        )

        percentiles: PercentileDict = {}

        for column in SIMILARITY_COLUMNS:
            percentiles[column] = st.slider(
                SLIDER_LABELS[column],
                min_value=0,
                max_value=100,
                value=DEFAULT_PERCENTILES[column],
                step=1,
            )

    archetype_summary = build_archetype_summary(position, percentiles)

    try:
        player_df = load_player_profiles()
        comps_df = find_similar_players(
            player_df,
            position,
            percentiles,
            top_n=top_n,
        )

        top_comp = get_comp_record(comps_df, 0)
        render_main_result(
            str(archetype_summary["archetype"]),
            str(top_comp["PLAYER_NAME"]),
            float(top_comp["SIMILARITY_SCORE"]),
        )

        left_col, right_col = st.columns([0.9, 1.35])

        with left_col:
            render_archetype_card(position, archetype_summary, percentiles)

        with right_col:
            st.subheader("Radar Comparison")

            comp_options = build_comp_options(comps_df)
            selected_label = cast(
                str,
                st.selectbox(
                    "Compare your chart against",
                    list(comp_options.keys()),
                ),
            )

            selected_comp = get_comp_record(comps_df, comp_options[selected_label])
            comp_percentiles = get_comp_percentiles(selected_comp)

            radar_fig = build_comparison_radar_chart(
                percentiles,
                comp_percentiles,
                str(selected_comp["PLAYER_NAME"]),
                title="Your Build vs Selected NBA Comp",
            )
            st.plotly_chart(radar_fig, width="stretch")

        st.divider()

        st.subheader("NBA Player Comps")
        st.caption("Ranked from most similar to least similar based on your selected build.")

        display_df = format_comps_table(comps_df)
        styled_df = display_df.style.apply(get_similarity_column_styles, axis=None)

        st.dataframe(
            styled_df,
            width="stretch",
            hide_index=True,
        )

    except FileNotFoundError:
        st.info(
            "Player comp data has not been exported yet. "
            "Create nba_comp_dashboard/data/player_similarity_profiles.csv first."
        )


if __name__ == "__main__":
    main()
