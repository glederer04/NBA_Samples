from __future__ import annotations

from typing import Dict, List, Union, cast

import pandas as pd
import streamlit as st

from src.archetypes import ArchetypeSummary, build_archetype_summary
from src.charts import build_comparison_radar_chart, build_radar_chart
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


PROFILE_TO_MODEL_POSITION = {
    "Guard/Wing": "SF",
    "Big": "C",
}


def add_page_styles() -> None:
    """Add small CSS tweaks."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"] {
            display: none;
        }

        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.4rem;
        }

        [data-testid="stSidebar"] .stSlider {
            padding-top: 0;
            padding-bottom: 0.1rem;
        }

        .main-result {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            padding: 1.15rem 1.35rem;
            background: linear-gradient(135deg, #111827 0%, #1f2937 58%, #7c2d12 100%);
            color: white;
            margin-bottom: 1rem;
        }

        .main-result-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #cbd5e1;
            margin-bottom: 0.25rem;
        }

        .main-result-title {
            font-size: 1.9rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }

        .main-result-subtitle {
            font-size: 1rem;
            color: #e5e7eb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_skill_label(skill: str) -> str:
    """Convert a percentile column into a readable skill name."""
    return SLIDER_LABELS.get(skill, skill.replace("_PCTL", "").replace("_", " ").title())


def get_top_skill(percentiles: PercentileDict) -> str:
    """Return the user's highest-rated skill label."""
    top_skill = max(percentiles, key=lambda column: float(percentiles[column]))
    return get_skill_label(top_skill)


def blend_score(
    user_percentiles: PercentileDict,
    comp_record: CompRecord,
    columns: List[str],
) -> int:
    """Blend user percentiles and top-comp percentiles into one card rating."""
    user_values = [float(user_percentiles[column]) for column in columns]
    comp_values = [float(comp_record[column]) for column in columns]
    blended_value = (sum(user_values) + sum(comp_values)) / (len(columns) * 2)

    return round(blended_value)


def get_card_ratings(
    user_percentiles: PercentileDict,
    comp_record: CompRecord,
) -> Dict[str, int]:
    """Create role ratings from user profile and top NBA comp."""
    return {
        "Shot Creation": blend_score(
            user_percentiles,
            comp_record,
            ["SCORING_PCTL", "CREATION_PCTL"],
        ),
        "Spacing": blend_score(
            user_percentiles,
            comp_record,
            ["SHOOTING_PCTL", "EFFICIENCY_PCTL"],
        ),
        "Playmaking": blend_score(
            user_percentiles,
            comp_record,
            ["PLAYMAKING_PCTL", "CREATION_PCTL"],
        ),
        "Rim Pressure": blend_score(
            user_percentiles,
            comp_record,
            ["RIM_PRESSURE_PCTL", "SCORING_PCTL"],
        ),
        "Glass Work": blend_score(
            user_percentiles,
            comp_record,
            ["REBOUNDING_PCTL"],
        ),
        "Defensive Impact": blend_score(
            user_percentiles,
            comp_record,
            ["DEFENSE_PCTL"],
        ),
    }


def get_role_summary(
    position_profile: str,
    archetype: str,
    comp_record: CompRecord,
    ratings: Dict[str, int],
) -> str:
    """Create a short role summary for the player card."""
    best_trait = max(ratings, key=lambda rating: ratings[rating])
    comp_name = str(comp_record["PLAYER_NAME"])

    if position_profile == "Big":
        return (
            f"{archetype} profile with {best_trait.lower()} as the clearest role signal. "
            f"The comp base is built from {comp_name}'s frontcourt profile."
        )

    return (
        f"{archetype} profile with {best_trait.lower()} driving the match. "
        f"The comp base is built from {comp_name}'s perimeter profile."
    )


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


def render_player_card(
    position_profile: str,
    archetype_summary: ArchetypeSummary,
    percentiles: PercentileDict,
    top_comp: CompRecord,
) -> None:
    """Render a compact player card."""
    ratings = get_card_ratings(percentiles, top_comp)
    overall = round(sum(ratings.values()) / len(ratings))
    archetype = str(archetype_summary["archetype"])
    role_summary = get_role_summary(position_profile, archetype, top_comp, ratings)

    with st.container(border=True):
        title_col, ovr_col = st.columns([0.68, 0.32])

        with title_col:
            st.caption(f"{position_profile.upper()} ROLE CARD")
            st.subheader(archetype)
            st.write(role_summary)

        with ovr_col:
            st.metric("OVR", overall)

        st.caption("Role Attribute Bars")

        for label, value in ratings.items():
            text_col, number_col = st.columns([0.75, 0.25])
            text_col.write(label)
            number_col.write(f"**{value}**")
            st.progress(value / 100)

        st.divider()

        st.caption("Signature Skill")
        st.write(f"**{get_top_skill(percentiles)}**")

        st.caption("Comp Base")
        st.write(f"**{str(top_comp['PLAYER_NAME'])}**")


def build_comp_options(comps_df: pd.DataFrame) -> Dict[str, int]:
    """Build selectbox labels for comp comparison."""
    options: Dict[str, int] = {"Just my build": -1}

    for index in range(len(comps_df)):
        row = cast(CompRecord, comps_df.iloc[index].to_dict())
        label = (
            f"{str(row['PLAYER_NAME'])} | {str(row['SEASON'])} "
            f"({str(row['TEAM_ABBREVIATION'])}) | "
            f"{float(row['SIMILARITY_SCORE']):.1f}"
        )
        options[label] = index

    return options


def rounded_numeric_values(
    display_df: pd.DataFrame,
    column: str,
    digits: int,
    multiplier: float = 1.0,
) -> List[float]:
    """Return rounded numeric values from one dataframe column."""
    numeric_values = cast(
        pd.Series,
        pd.to_numeric(display_df[column], errors="coerce"),
    )

    return [
        round(float(value) * multiplier, digits) if pd.notna(value) else 0.0
        for value in numeric_values
    ]


def rounded_integer_values(display_df: pd.DataFrame, column: str) -> List[int]:
    """Return rounded integer values from one dataframe column."""
    numeric_values = cast(
        pd.Series,
        pd.to_numeric(display_df[column], errors="coerce"),
    )

    return [
        round(float(value)) if pd.notna(value) else 0
        for value in numeric_values
    ]


def format_comps_table(comps_df: pd.DataFrame) -> pd.DataFrame:
    """Format and reorder the comps table for display."""
    table_columns = [
        "PLAYER_NAME",
        "SEASON",
        "TEAM_ABBREVIATION",
        "POSITION",
        "AGE",
        "SIMILARITY_SCORE",
        "PTS",
        "REB",
        "AST",
        "TS_PCT",
        "USG_PCT",
    ]

    display_df = cast(pd.DataFrame, comps_df.loc[:, table_columns].copy())

    display_df["AGE"] = rounded_integer_values(display_df, "AGE")
    display_df["SIMILARITY_SCORE"] = rounded_numeric_values(
        display_df,
        "SIMILARITY_SCORE",
        1,
    )
    display_df["PTS"] = rounded_numeric_values(display_df, "PTS", 1)
    display_df["REB"] = rounded_numeric_values(display_df, "REB", 1)
    display_df["AST"] = rounded_numeric_values(display_df, "AST", 1)
    display_df["TS_PCT"] = rounded_numeric_values(display_df, "TS_PCT", 1, 100)
    display_df["USG_PCT"] = rounded_numeric_values(display_df, "USG_PCT", 1, 100)

    display_df.columns = [
        "Player",
        "Season",
        "Team",
        "Position",
        "Age",
        "Similarity",
        "PTS",
        "REB",
        "AST",
        "TS%",
        "USG%",
    ]

    return display_df


def style_comps_table(display_df: pd.DataFrame) -> pd.DataFrame:
    """Style the comps table."""
    styles = pd.DataFrame("", index=display_df.index, columns=display_df.columns)

    for column in display_df.columns:
        styles[column] = "text-align: center;"

    styles["Similarity"] = (
        "background-color: #DBEAFE; color: #111827; font-weight: 800; "
        "text-align: center;"
    )
    styles["Age"] = "text-align: left;"

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

        position_profile = cast(
            str,
            st.segmented_control(
                "Position",
                cast(List[str], ["Guard/Wing", "Big"]),
                default="Guard/Wing",
            ),
        )

        model_position = PROFILE_TO_MODEL_POSITION[position_profile]

        percentiles: PercentileDict = {}

        for column in SIMILARITY_COLUMNS:
            percentiles[column] = st.slider(
                SLIDER_LABELS[column],
                min_value=0,
                max_value=100,
                value=DEFAULT_PERCENTILES[column],
                step=1,
            )

    archetype_summary = build_archetype_summary(model_position, percentiles)

    try:
        player_df = load_player_profiles()

        max_comps_df = find_similar_players(
            player_df,
            model_position,
            percentiles,
            top_n=25,
        )

        selected_top_n = int(st.session_state.get("top_n", 5))
        comps_df = max_comps_df.head(selected_top_n).reset_index(drop=True)

        top_comp = get_comp_record(comps_df, 0)

        render_main_result(
            str(archetype_summary["archetype"]),
            str(top_comp["PLAYER_NAME"]),
            float(top_comp["SIMILARITY_SCORE"]),
        )

        left_col, right_col = st.columns([0.9, 1.35])

        with left_col:
            render_player_card(
                position_profile,
                archetype_summary,
                percentiles,
                top_comp,
            )

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

            selected_index = comp_options[selected_label]

            if selected_index == -1:
                radar_fig = build_radar_chart(
                    percentiles,
                    title="Your Build Profile",
                )
            else:
                selected_comp = get_comp_record(comps_df, selected_index)
                comp_percentiles = get_comp_percentiles(selected_comp)

                radar_fig = build_comparison_radar_chart(
                    percentiles,
                    comp_percentiles,
                    str(selected_comp["PLAYER_NAME"]),
                    title="Your Build vs Selected NBA Comp",
                )

            st.plotly_chart(
                radar_fig,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        st.divider()

        top_n = cast(
            int,
            st.radio(
                "Number of comps",
                cast(List[int], [5, 10, 25]),
                horizontal=True,
                key="top_n",
            ),
        )

        comps_df = max_comps_df.head(top_n).reset_index(drop=True)

        st.subheader("NBA Player Comps")
        st.caption("Ranked from most similar to least similar based on your selected build.")

        display_df = format_comps_table(comps_df)
        styled_df = (
            display_df.style.apply(style_comps_table, axis=None)
            .set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [("text-align", "center")],
                    }
                ]
            )
            .format(
                {
                    "Age": "{:.0f}",
                    "Similarity": "{:.1f}",
                    "PTS": "{:.1f}",
                    "REB": "{:.1f}",
                    "AST": "{:.1f}",
                    "TS%": "{:.1f}",
                    "USG%": "{:.1f}",
                }
            )
        )

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