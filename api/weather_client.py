import datetime
import json
import time
from pathlib import Path
import requests
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from config import config
from .constants import (
    CONDITION_TO_ICON,
    WEEKDAYS_SHORT,
    YANDEX_CONDITION_NAMES,
    degree_to_wind_arrow,
    degree_to_wind_direction,
    owm_code_to_condition,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "weather_cache.json"


def fetch_openweathermap(lat: float, lon: float, api_key: str) -> dict:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "rpi-dashboard/1.0 (https://github.com/mucxep/rpi-dashboard)"
    })

    current_resp = session.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
            "lang": "ru",
        },
        timeout=10,
    )
    current_resp.raise_for_status()
    current_data = current_resp.json()

    forecast_resp = session.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
            "lang": "ru",
        },
        timeout=10,
    )
    forecast_resp.raise_for_status()
    forecast_data = forecast_resp.json()

    weather_list = current_data.get("weather", [])
    primary_weather = weather_list[0] if weather_list else {}
    condition = owm_code_to_condition(primary_weather.get("id", 800))
    desc = primary_weather.get("description", "")
    condition_name = desc.capitalize() if desc else YANDEX_CONDITION_NAMES.get(condition, "Ясно")

    main_info = current_data.get("main", {})
    wind_info = current_data.get("wind", {})
    wind_angle = wind_info.get("deg", 0)

    fact = {
        "temp": round(main_info.get("temp", 0)),
        "feels_like": round(
            main_info.get("feels_like", main_info.get("temp", 0))
        ),
        "condition": condition,
        "condition_name": condition_name,
        "icon": CONDITION_TO_ICON.get(condition, "skc_d"),
        "wind_speed": round(float(wind_info.get("speed", 0)), 1),
        "wind_dir": degree_to_wind_direction(wind_angle),
        "wind_arrow": degree_to_wind_arrow(wind_angle),
        "wind_angle": wind_angle,
        "pressure_mm": round(float(main_info.get("pressure", 1013.25)) * 0.750062),
        "humidity": round(main_info.get("humidity", 50)),
    }

    grouped_days = {}
    for entry in forecast_data.get("list", []):
        dt_txt = entry.get("dt_txt", "")
        if " " not in dt_txt:
            continue
        date_str, time_str = dt_txt.split(" ", 1)
        if date_str not in grouped_days:
            grouped_days[date_str] = []
        grouped_days[date_str].append((time_str, entry))

    date_keys = list(grouped_days.keys())
    selected_dates = date_keys[1:6] if len(date_keys) > 5 else date_keys[:5]

    forecast_days = []
    for date_str in selected_dates:
        entries = grouped_days[date_str]
        min_temp = min(
            e.get("main", {}).get("temp_min", e.get("main", {}).get("temp", 0))
            for _, e in entries
        )
        max_temp = max(
            e.get("main", {}).get("temp_max", e.get("main", {}).get("temp", 0))
            for _, e in entries
        )

        def hour_diff(item):
            t_str, _ = item
            try:
                hour = int(t_str.split(":")[0])
                return abs(hour - 14)
            except Exception:
                return 99

        _, best_entry = min(entries, key=hour_diff)
        best_w = best_entry.get("weather", [{}])[0]
        f_cond = owm_code_to_condition(best_w.get("id", 800))
        f_desc = best_w.get("description", "")
        f_cond_text = f_desc.capitalize() if f_desc else YANDEX_CONDITION_NAMES.get(f_cond, "Ясно")

        day_name = ""
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

    return {"source": "openweathermap", "fact": fact, "forecast": forecast_days}


class WeatherWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        lat, lon = config.WEATHER_LAT, config.WEATHER_LON
        api_key = config.OPENWEATHER_API_KEY
        if lat is None or lon is None:
            self.failed.emit("Координаты не заданы")
            return
        if not api_key:
            self.failed.emit("Не задан OPENWEATHER_API_KEY")
            return

        try:
            payload = fetch_openweathermap(lat, lon, api_key)
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
        if not config.OPENWEATHER_API_KEY:
            self.weather_error.emit(
                "API-ключ OPENWEATHER_API_KEY не задан в .env"
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
