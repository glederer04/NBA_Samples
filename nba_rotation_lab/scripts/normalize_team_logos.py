"""Create consistently padded UI/report assets from the bundled official PNGs."""

from PIL import Image

from rotation_lab.config import ASSETS_DIR


def main() -> None:
    source = ASSETS_DIR / "team-logos"
    target = source / "normalized"
    target.mkdir(exist_ok=True)
    for path in source.glob("*.png"):
        with Image.open(path) as image:
            logo = image.convert("RGBA")
            logo = logo.crop(logo.getchannel("A").getbbox())
            scale = 160 / max(logo.size)
            logo = logo.resize(
                (round(logo.width * scale), round(logo.height * scale)), Image.Resampling.LANCZOS
            )
            canvas = Image.new("RGBA", (192, 192))
            canvas.alpha_composite(logo, ((192 - logo.width) // 2, (192 - logo.height) // 2))
            canvas.save(target / path.name)


if __name__ == "__main__":
    main()
