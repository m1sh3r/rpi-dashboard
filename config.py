import os
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
env_path = base_dir / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    PORT = int(os.getenv("PORT", "3000"))
    PC_STATUS_TOKEN = os.getenv("PC_STATUS_TOKEN", "change-me")
    PC_STATUS_STALE_AFTER_MS = int(os.getenv("PC_STATUS_STALE_AFTER_MS", "30000"))

    YANDEX_WEATHER_API_KEY = os.getenv("YANDEX_WEATHER_API_KEY", "")
    YANDEX_WEATHER_API_ENDPOINT = os.getenv(
        "YANDEX_WEATHER_API_ENDPOINT", "https://api.weather.yandex.ru/v2/forecast"
    )
    YANDEX_WEATHER_LANG = os.getenv("YANDEX_WEATHER_LANG", "ru_RU")
    YANDEX_WEATHER_REFRESH_MS = int(os.getenv("YANDEX_WEATHER_REFRESH_MS", "3600000"))
    YANDEX_DAILY_LIMIT = int(os.getenv("YANDEX_DAILY_LIMIT", "30"))

    WEATHER_LAT = float(os.getenv("WEATHER_LAT")) if os.getenv("WEATHER_LAT") else None
    WEATHER_LON = float(os.getenv("WEATHER_LON")) if os.getenv("WEATHER_LON") else None

    DASHBOARD_LOCALE = os.getenv("DASHBOARD_LOCALE", "ru_RU")
    WEEK_STARTS_ON = int(os.getenv("WEEK_STARTS_ON", "1"))
    WINDOW_WIDTH = int(os.getenv("WINDOW_WIDTH", "1920"))
    WINDOW_HEIGHT = int(os.getenv("WINDOW_HEIGHT", "480"))


config = Config()
