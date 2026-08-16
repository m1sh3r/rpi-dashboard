import os
from pathlib import Path
import requests
from PyQt5.QtSvg import QSvgRenderer
from api.constants import CONDITION_TO_ICON

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache" / "weather_icons"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YANDEX_ICON_URL = "https://yastatic.net/weather/i/icons/funky/flat/{}.svg"

_RENDERER_CACHE = {}


def get_icon_renderer(icon_code: str = None, condition: str = None) -> QSvgRenderer:
    code = icon_code or CONDITION_TO_ICON.get(condition, "skc_d")
    if not code:
        code = "skc_d"

    if code in _RENDERER_CACHE:
        return _RENDERER_CACHE[code]

    local_path = CACHE_DIR / f"{code}.svg"
    if not local_path.exists() or local_path.stat().st_size == 0:
        try:
            url = YANDEX_ICON_URL.format(code)
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200 and resp.content:
                local_path.write_bytes(resp.content)
        except Exception:
            pass

    if local_path.exists() and local_path.stat().st_size > 0:
        renderer = QSvgRenderer(str(local_path))
        if renderer.isValid():
            _RENDERER_CACHE[code] = renderer
            return renderer

    return None
