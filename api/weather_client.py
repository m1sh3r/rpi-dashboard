import datetime
import json
from pathlib import Path
import requests
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from config import config
from .constants import (
    CONDITION_TO_ICON,
    WEEKDAYS_SHORT,
    WMO_TO_YANDEX_CONDITION,
    YANDEX_CONDITION_NAMES,
    degree_to_wind_arrow,
    degree_to_wind_direction,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "weather_cache.json"


def fetch_open_meteo(lat: float, lon: float) -> dict:
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "pressure_msl,wind_speed_10m,wind_direction_10m,weather_code"
            ),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": 6,
        },
        headers={
            "User-Agent": "rpi-dashboard/1.0 (https://github.com/mucxep/rpi-dashboard)"
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    current = data.get("current", {})
    wmo_code = int(current.get("weather_code", 0))
    condition = WMO_TO_YANDEX_CONDITION.get(wmo_code, "clear")
    condition_name = YANDEX_CONDITION_NAMES.get(condition, "Ясно")
    wind_angle = current.get("wind_direction_10m", 0) or 0

    fact = {
        "temp": round(current.get("temperature_2m", 0)),
        "feels_like": round(
            current.get("apparent_temperature", current.get("temperature_2m", 0))
        ),
        "condition": condition,
        "condition_name": condition_name,
        "icon": CONDITION_TO_ICON.get(condition, "skc_d"),
        "wind_speed": round(float(current.get("wind_speed_10m", 0) or 0), 1),
        "wind_dir": degree_to_wind_direction(wind_angle),
        "wind_arrow": degree_to_wind_arrow(wind_angle),
        "wind_angle": wind_angle,
        "pressure_mm": round(
            float(current.get("pressure_msl", 1013.25) or 1013.25) * 0.750062
        ),
        "humidity": round(current.get("relative_humidity_2m", 50) or 50),
    }

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    codes = daily.get("weather_code", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])

    start_idx = 1 if len(dates) > 5 else 0
    end_idx = start_idx + 5

    forecast_days = []
    for i in range(start_idx, min(end_idx, len(dates))):
        date_str = dates[i]
        f_code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
        f_cond = WMO_TO_YANDEX_CONDITION.get(f_code, "clear")
        f_cond_text = YANDEX_CONDITION_NAMES.get(f_cond, "Ясно")
        max_temp = (
            max_temps[i] if i < len(max_temps) and max_temps[i] is not None else 0
        )
        min_temp = (
            min_temps[i] if i < len(min_temps) and min_temps[i] is not None else 0
        )

        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            day_name = WEEKDAYS_SHORT[dt.weekday()]
        except Exception:
            day_name = date_str

        forecast_days.append(
            {
                "date": date_str,
                "day_name": day_name,
                "max_temp": round(max_temp),
                "min_temp": round(min_temp),
                "condition": f_cond,
                "cond_text": f_cond_text,
                "icon": CONDITION_TO_ICON.get(f_cond, "skc_d"),
            }
        )

    return {"source": "open-meteo", "fact": fact, "forecast": forecast_days}


class WeatherWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        lat, lon = config.WEATHER_LAT, config.WEATHER_LON
        if lat is None or lon is None:
            self.failed.emit("Координаты не заданы")
            return

        try:
            payload = fetch_open_meteo(lat, lon)
            try:
                CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
            except Exception:
                pass
            self.finished.emit(payload)
        except Exception:
            if CACHE_FILE.exists():
                try:
                    cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                    self.finished.emit(cached)
                    return
                except Exception:
                    pass
            self.failed.emit("Ошибка сети")


class WeatherClient(QObject):
    weather_updated = pyqtSignal(dict)
    weather_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cached_payload = None
        self.worker = None

        if CACHE_FILE.exists():
            try:
                self._cached_payload = json.loads(
                    CACHE_FILE.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        self.timer = QTimer(self)
        self.timer.setInterval(config.WEATHER_REFRESH_MS)
        self.timer.timeout.connect(self.update_weather)
        self.timer.start()

    def get_cached_payload(self) -> dict | None:
        return self._cached_payload

    def update_weather(self):
        if config.WEATHER_LAT is None or config.WEATHER_LON is None:
            self.weather_error.emit(
                "Координаты WEATHER_LAT и WEATHER_LON не заданы в .env"
            )
            return
        if self.worker and self.worker.isRunning():
            return
        self.worker = WeatherWorker()
        self.worker.finished.connect(self._on_success)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _on_success(self, payload):
        self._cached_payload = payload
        self.weather_updated.emit(payload)

    def _on_fail(self, error):
        if self._cached_payload:
            self.weather_updated.emit(self._cached_payload)
        else:
            self.weather_error.emit(error)
