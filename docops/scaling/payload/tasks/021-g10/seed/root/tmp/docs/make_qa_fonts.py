"""Create local Aptos-named font substitutes for accurate visual QA rendering.

The presentation remains unchanged and continues to specify Aptos/Aptos Display.
These fonts are only installed in the QA environment because the proprietary
Microsoft families are not present in the container.
"""

from pathlib import Path

from fontTools.ttLib import TTFont


FONT_DIR = Path("/root/tmp/docs/qa_fonts")
FONT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = {
    "regular": Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    "bold": Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
}


def rename_font(source: Path, family: str, style: str, output: Path) -> None:
    font = TTFont(source)
    full_name = f"{family} {style}"
    postscript_name = f"{family.replace(' ', '')}-{style}"
    names = font["name"]
    values = {
        1: family,
        2: style,
        3: full_name.replace(" ", "") + ";QA",
        4: full_name,
        6: postscript_name,
        16: family,
        17: style,
    }
    for name_id, value in values.items():
        names.setName(value, name_id, 3, 1, 0x409)
        names.setName(value, name_id, 1, 0, 0)
        names.setName(value, name_id, 0, 3, 0)
    font.save(output)
    print(f"Wrote {output}")


for family, slug in (("Aptos", "Aptos"), ("Aptos Display", "AptosDisplay")):
    for style, source in SOURCES.items():
        output = FONT_DIR / f"{slug}-{style}.ttf"
        rename_font(source, family, style.title(), output)
