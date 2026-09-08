"""Compact names and consistent local logo assets."""

from PIL import Image

from rotation_lab.config import ASSETS_DIR
from rotation_lab.dashboard.components import compact_lineup_names, team_logo


def test_compact_names_keep_suffixes_and_disambiguate_collisions():
    assert compact_lineup_names("OG Anunoby | Jalen Brunson") == "OG Anunoby · J. Brunson"
    assert compact_lineup_names("Karl-Anthony Towns | Gary Trent Jr. | Jalen Brunson") == (
        "K. Towns · G. Trent Jr. · J. Brunson"
    )
    assert compact_lineup_names("Jalen Williams | Jaylin Williams") == (
        "Jalen Williams · Jaylin Williams"
    )


def test_all_team_logos_have_consistent_canvas_and_visible_artwork():
    files = list((ASSETS_DIR / "team-logos" / "normalized").glob("*.png"))
    assert len(files) == 30
    for path in files:
        with Image.open(path) as logo:
            assert logo.size == (192, 192)
            bounds = logo.getchannel("A").getbbox()
            assert bounds is not None
            assert max(bounds[2] - bounds[0], bounds[3] - bounds[1]) == 160
    logo = team_logo("NYK")
    assert logo.width == logo.height == 28
    assert "/normalized/NYK.png" in logo.src
    assert "team-placeholder" in team_logo("UNKNOWN").src
