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
    WMO_TO_YANDEX_CONDITION,
    YANDEX_CONDITION_NAMES,
    degree_to_wind_direction,
)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "weather_cache.json"
META_FILE = CACHE_DIR / "weather_request_meta.json"


def can_make_yandex_request():
    today_key = datetime.date.today().strftime("%Y-%m-%d")
    meta = {"dateKey": today_key, "count": 0}
    if META_FILE.exists():
        try:
            data = json.loads(META_FILE.read_text(encoding="utf-8"))
            if data.get("dateKey") == today_key:
                meta = data
        except Exception:
            pass
    return meta.get("count", 0) < config.YANDEX_DAILY_LIMIT, meta


def record_yandex_request(meta):
    today_key = datetime.date.today().strftime("%Y-%m-%d")
    if meta.get("dateKey") != today_key:
        meta = {"dateKey": today_key, "count": 1}
    else:
        meta["count"] = meta.get("count", 0) + 1
    try:
        META_FILE.write_text(json.dumps(meta), encoding="utf-8")
    except Exception:
        pass


class WeatherWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        lat, lon = config.WEATHER_LAT, config.WEATHER_LON
        if lat is None or lon is None:
            self.failed.emit("Координаты WEATHER_LAT и WEATHER_LON не заданы в .env")
            return

        payload = None
        has_budget, meta = can_make_yandex_request()

        if config.YANDEX_WEATHER_API_KEY and has_budget:
            try:
                params = {
                    "lat": lat,
                    "lon": lon,
                    "lang": config.YANDEX_WEATHER_LANG,
                    "limit": 1,
                    "hours": "false",
                    "extra": "false",
                }
                headers = {"X-Yandex-Weather-Key": config.YANDEX_WEATHER_API_KEY}
                resp = requests.get(
                    config.YANDEX_WEATHER_API_ENDPOINT,
                    params=params,
                    headers=headers,
                    timeout=10,
                )
                if resp.status_code == 200:
                    record_yandex_request(meta)
                    data = resp.json()
                    fact = data.get("fact", {})
                    cond = fact.get("condition", "clear")
                    payload = {
                        "source": "yandex",
                        "fact": {
                            "temp": round(fact.get("temp", 0)),
                            "feels_like": round(fact.get("feels_like", 0)),
                            "condition": cond,
                            "condition_name": YANDEX_CONDITION_NAMES.get(
                                cond, fact.get("condition", "Ясно")
                            ),
                            "icon": fact.get("icon")
                            or CONDITION_TO_ICON.get(cond, "skc_d"),
                            "wind_speed": float(fact.get("wind_speed", 0)),
                            "wind_dir": degree_to_wind_direction(
                                fact.get("wind_angle", 0)
                            ),
                            "wind_angle": fact.get("wind_angle", 0),
                            "pressure_mm": fact.get("pressure_mm", 750),
                            "humidity": fact.get("humidity", 50),
                        },
                    }
            except Exception:
                payload = None

        if not payload:
            try:
                url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,pressure_msl,wind_speed_10m,wind_direction_10m"
                    "&timezone=auto"
                )
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                current = data.get("current", {})
                condition = WMO_TO_YANDEX_CONDITION.get(
                    current.get("weather_code", 0), "overcast"
                )
                payload = {
                    "source": "open-meteo",
                    "fact": {
                        "temp": round(current.get("temperature_2m", 0)),
                        "feels_like": round(
                            current.get(
                                "apparent_temperature", current.get("temperature_2m", 0)
                            )
                        ),
                        "condition": condition,
                        "condition_name": YANDEX_CONDITION_NAMES.get(condition, "Ясно"),
                        "icon": CONDITION_TO_ICON.get(condition, "skc_d"),
                        "wind_speed": round(
                            float(current.get("wind_speed_10m", 0)) / 3.6, 1
                        ),
                        "wind_dir": degree_to_wind_direction(
                            current.get("wind_direction_10m", 0)
                        ),
                        "wind_angle": current.get("wind_direction_10m", 0),
                        "pressure_mm": round(
                            float(current.get("pressure_msl", 1013.25)) * 0.750062
                        ),
                        "humidity": round(current.get("relative_humidity_2m", 50)),
                    },
                }
            except Exception as e:
                if CACHE_FILE.exists():
                    try:
                        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                        self.finished.emit(cached)
                        return
                    except Exception:
                        pass
                self.failed.emit(str(e))
                return

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto"
            )
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            times = daily.get("time", [])
            codes = daily.get("weather_code", [])
            temp_maxs = daily.get("temperature_2m_max", [])
            temp_mins = daily.get("temperature_2m_min", [])

            forecast_days = []
            start_idx = 1 if len(times) > 5 else 0
            for i in range(start_idx, min(len(times), start_idx + 5)):
                f_cond = WMO_TO_YANDEX_CONDITION.get(
                    codes[i] if i < len(codes) else 0, "clear"
                )
                date_str = times[i] if i < len(times) else ""
                day_name = ""
                try:
                    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    day_name = WEEKDAYS_SHORT[dt.weekday()]
                except Exception:
                    day_name = f"Д{i}"

                forecast_days.append(
                    {
                        "date": date_str,
                        "day_name": day_name,
                        "max_temp": round(temp_maxs[i]) if i < len(temp_maxs) else 0,
                        "min_temp": round(temp_mins[i]) if i < len(temp_mins) else 0,
                        "condition": f_cond,
                        "cond_text": YANDEX_CONDITION_NAMES.get(f_cond, "Ясно"),
                        "icon": CONDITION_TO_ICON.get(f_cond, "skc_d"),
                    }
                )
            payload["forecast"] = forecast_days
        except Exception:
            payload["forecast"] = []

        try:
            CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

        self.finished.emit(payload)


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
        self.timer.setInterval(config.YANDEX_WEATHER_REFRESH_MS)
        self.timer.timeout.connect(self.update_weather)
        self.timer.start()

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
