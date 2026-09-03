from pathlib import Path
import threading
import requests
from PyQt5.QtSvg import QSvgRenderer
from api.constants import CONDITION_TO_ICON

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache" / "weather_icons"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YANDEX_ICON_URL = "https://yastatic.net/weather/i/icons/funky/dark/{}.svg"

_RENDERER_CACHE = {}
_PENDING_DOWNLOADS = set()
_LOCK = threading.Lock()


def _download_icon(code: str, callback=None):
    local_path = CACHE_DIR / f"{code}.svg"
    try:
        url = YANDEX_ICON_URL.format(code)
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and resp.content:
            local_path.write_bytes(resp.content)
            renderer = QSvgRenderer(str(local_path))
            if renderer.isValid():
                with _LOCK:
                    _RENDERER_CACHE[code] = renderer
                if callback:
                    callback()
    except Exception:
        pass
    finally:
        with _LOCK:
            _PENDING_DOWNLOADS.discard(code)


def get_icon_renderer(
    icon_code: str | None = None, condition: str | None = None, on_loaded=None
) -> QSvgRenderer | None:
    code = icon_code or (CONDITION_TO_ICON.get(condition, "skc_d") if condition else "skc_d")
    if not code:
        code = "skc_d"

    with _LOCK:
        if code in _RENDERER_CACHE:
            return _RENDERER_CACHE[code]

    local_path = CACHE_DIR / f"{code}.svg"
    if local_path.exists() and local_path.stat().st_size > 0:
        renderer = QSvgRenderer(str(local_path))
        if renderer.isValid():
            with _LOCK:
                _RENDERER_CACHE[code] = renderer
            return renderer

    with _LOCK:
        if code not in _PENDING_DOWNLOADS:
            _PENDING_DOWNLOADS.add(code)
            t = threading.Thread(target=_download_icon, args=(code, on_loaded), daemon=True)
            t.start()

    return None
