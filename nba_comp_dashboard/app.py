from __future__ import annotations

from typing import Dict, List, Union, cast

import pandas as pd
import plotly.graph_objects as go
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
        .block-container {
            padding-top: 1.25rem;
        }

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

        h1 {
            margin-top: 0;
            padding-top: 0;
        }

        .main-result {
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            padding: 1rem 1.25rem;
            background: linear-gradient(135deg, #111827 0%, #1f2937 58%, #7c2d12 100%);
            color: white;
            margin-bottom: 0.85rem;
        }

        .main-result-label {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #cbd5e1;
            margin-bottom: 0.2rem;
        }

        .main-result-title {
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1.08;
            margin-bottom: 0.3rem;
        }

        .main-result-subtitle {
            font-size: 0.98rem;
            color: #e5e7eb;
        }

        div[data-testid="stDivider"] {
            margin-top: -0.45rem !important;
            margin-bottom: -0.65rem !important;
        }

        div[data-testid="stDivider"] hr {
            margin-top: 0.15rem !important;
            margin-bottom: 0.15rem !important;
        }

        .overall-box {
            background: linear-gradient(135deg, #f97316 0%, #facc15 100%);
            border: 2px solid rgba(255, 255, 255, 0.24);
            border-radius: 8px;
            box-shadow: 0 10px 22px rgba(249, 115, 22, 0.26);
            padding: 0.7rem 0.55rem;
            text-align: center;
        }

        .overall-label {
            color: #111827;
            font-size: 0.82rem !important;
            font-weight: 900;
            letter-spacing: 0.08em;
            line-height: 1;
            margin-bottom: 0.25rem;
            text-transform: uppercase;
        }

        .overall-value {
            color: #111827;
            font-size: 2.45rem !important;
            font-weight: 950;
            line-height: 1;
        }

        .rating-label {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 850;
            line-height: 1;
            margin-bottom: 0.35rem;
        }

        .rating-value {
            color: #f9fafb;
            font-size: 1rem;
            font-weight: 950;
            line-height: 1;
            margin-bottom: 0.35rem;
            text-align: right;
        }

        .footer-value {
            color: #f9fafb;
            font-size: 1.25rem !important;
            font-weight: 850;
            line-height: 1;
            margin-top: -0.75rem !important;
            margin-bottom: -0.2rem !important;
        }

        div[data-testid="stProgress"] {
            margin-top: -0.35rem;
            margin-bottom: -0.42rem;
        }

        div[data-testid="stProgress"] > div {
            height: 0.45rem;
        }

        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #f97316 0%, #facc15 100%);
            border: 1px solid rgba(255, 255, 255, 0.24);
            border-radius: 8px;
            box-shadow: 0 8px 18px rgba(249, 115, 22, 0.22);
            padding: 0.55rem 0.5rem;
            text-align: center;
        }

        div[data-testid="stMetric"] label {
            color: #111827;
            display: flex;
            font-weight: 900;
            justify-content: center;
            letter-spacing: 0.08em;
            text-align: center;
            text-transform: uppercase;
            width: 100%;
        }

        div[data-testid="stMetricValue"] {
            color: #111827;
            display: flex;
            font-size: 2rem;
            font-weight: 950;
            justify-content: center;
            line-height: 1;
            text-align: center;
            width: 100%;
        }

        div[data-testid="stTable"] th {
            text-align: center !important;
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
    comp_record: CompRecord,
    ratings: Dict[str, int],
) -> str:
    """Create a short role summary from the user build and closest comp."""
    sorted_traits = sorted(ratings, key=lambda rating: ratings[rating], reverse=True)
    best_trait = sorted_traits[0]
    second_trait = sorted_traits[1]
    comp_name = str(comp_record["PLAYER_NAME"])

    return (
        f"Your inputs and {comp_name}'s match point toward a {best_trait.lower()}-first "
        f"{position_profile.lower()} with {second_trait.lower()} as the support skill."
    )


def render_intro() -> None:
    """Render the short explanation section."""
    st.title("NBA Player Comp Dashboard")
    st.markdown(
        """
        Build a quick player profile, then see which NBA player-seasons your game most closely matches.
        Use the sliders as percentiles relative to the people you actually play with, like pickup runs,
        rec league, school team, or your workout group.
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
    role_summary = get_role_summary(position_profile, top_comp, ratings)

    with st.container(border=True):
        title_col, overall_col = st.columns([0.72, 0.28], vertical_alignment="center")

        with title_col:
            st.caption(f"{position_profile.upper()} ROLE CARD")
            st.subheader(archetype)
            st.caption(role_summary)

        with overall_col:
            st.metric("Overall", overall)

        st.divider()

        for label, value in ratings.items():
            label_col, value_col = st.columns([0.78, 0.22], vertical_alignment="bottom")

            with label_col:
                st.markdown(f'<p class="rating-label">{label}</p>', unsafe_allow_html=True)

            with value_col:
                st.markdown(f'<p class="rating-value">{value}</p>', unsafe_allow_html=True)

            st.progress(value / 100)

        st.divider()

        footer_col_1, footer_col_2 = st.columns(2)

        with footer_col_1:
            st.caption("Signature Skill")
            st.markdown(
                f'<p class="footer-value">{get_top_skill(percentiles)}</p>',
                unsafe_allow_html=True,
            )

        with footer_col_2:
            st.caption("Comp Base")
            st.markdown(
                f'<p class="footer-value">{str(top_comp["PLAYER_NAME"])}</p>',
                unsafe_allow_html=True,
            )


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

    styles["Player"] = "text-align: left;"
    styles["Age"] = "text-align: left !important;"
    styles["Similarity"] = (
        "background-color: #d14f0f; color: #111827; font-weight: 800; text-align: center !important;"
    )

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


def style_radar_chart_ticks(radar_fig: go.Figure) -> go.Figure:
    """Style radar chart labels and grid."""
    radar_fig.update_layout(
        font=dict(color="#f9fafb"),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[0, 25, 50, 75, 100],
                showticklabels=True,
                tickfont=dict(color="#111827", size=11),
                gridcolor="rgba(17, 24, 39, 0.35)",
                linecolor="rgba(17, 24, 39, 0.45)",
            ),
            angularaxis=dict(
                visible=True,
                showticklabels=True,
                tickfont=dict(color="#f9fafb", size=13),
                gridcolor="rgba(17, 24, 39, 0.25)",
                linecolor="rgba(17, 24, 39, 0.45)",
            ),
        ),
    )

    return radar_fig


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

            radar_fig = style_radar_chart_ticks(radar_fig)

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
        display_df.index = range(1, len(display_df) + 1)
        styled_df = (
            display_df.style.apply(style_comps_table, axis=None)
            .hide(axis="index")
            .set_table_styles(
                [
                    {
                        "selector": "th",
                        "props": [
                            ("text-align", "center"),
                            ("font-weight", "800"),
                        ],
                    },
                    {
                        "selector": "td",
                        "props": [
                            ("vertical-align", "middle"),
                        ],
                    },
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

        st.table(styled_df)

    except FileNotFoundError:
        st.info(
            "Player comp data has not been exported yet. "
            "Create nba_comp_dashboard/data/player_similarity_profiles.csv first."
        )


if __name__ == "__main__":
    main()