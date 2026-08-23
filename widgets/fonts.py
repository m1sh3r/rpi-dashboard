from pathlib import Path
from PyQt5.QtGui import QFont, QFontDatabase

FONT_FAMILY_BY_WEIGHT = {
    100: "Inter Thin",
    200: "Inter ExtraLight",
    300: "Inter Light",
    400: "Inter",
    500: "Inter Medium",
    600: "Inter SemiBold",
    700: "Inter",
    800: "Inter ExtraBold",
    900: "Inter Black",
}


def load_fonts():
    fonts_dir = Path(__file__).resolve().parent.parent / "fonts"
    if not fonts_dir.exists():
        return
    for font_file in fonts_dir.rglob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))


def get_inter_font(
    size: int = 12,
    weight: int = 400,
    italic: bool = False,
    is_pixel_size: bool = False,
) -> QFont:
    if weight == QFont.Thin:
        weight = 100
    elif weight == QFont.ExtraLight:
        weight = 200
    elif weight == QFont.Light:
        weight = 300
    elif weight == QFont.Normal:
        weight = 400
    elif weight == QFont.Medium:
        weight = 500
    elif weight == QFont.DemiBold:
        weight = 600
    elif weight == QFont.Bold:
        weight = 700
    elif weight == QFont.ExtraBold:
        weight = 800
    elif weight == QFont.Black:
        weight = 900

    family = FONT_FAMILY_BY_WEIGHT.get(weight, "Inter")
    font = QFont(family)
    if is_pixel_size:
        font.setPixelSize(size)
    else:
        font.setPointSize(size)

    if weight >= 700:
        font.setBold(True)
    if italic:
        font.setItalic(True)
    return font
