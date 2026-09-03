import os
from pathlib import Path
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
env_path = base_dir / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    PORT = int(os.getenv("PORT", "3000"))
    PC_STATUS_SERVER_PORT = int(
        os.getenv("PC_STATUS_SERVER_PORT", os.getenv("PORT", "3000"))
    )
    PC_STATUS_ENDPOINT = os.getenv(
        "PC_STATUS_ENDPOINT", "http://localhost:3000/api/pc-status"
    )
    PC_STATUS_TOKEN = os.getenv("PC_STATUS_TOKEN", "change-me")
    PC_STATUS_REFRESH_MS = int(os.getenv("PC_STATUS_REFRESH_MS", "1000"))
    PC_STATUS_STALE_AFTER_MS = int(os.getenv("PC_STATUS_STALE_AFTER_MS", "30000"))

    WEATHER_REFRESH_MS = int(os.getenv("WEATHER_REFRESH_MS", "300000"))

    WEATHER_LAT: float | None = float(v) if (v := os.getenv("WEATHER_LAT")) else None
    WEATHER_LON: float | None = float(v) if (v := os.getenv("WEATHER_LON")) else None

    DASHBOARD_LOCALE = os.getenv("DASHBOARD_LOCALE", "ru_RU")
    WEEK_STARTS_ON = int(os.getenv("WEEK_STARTS_ON", "1"))
    WINDOW_WIDTH = int(os.getenv("WINDOW_WIDTH", "1920"))
    WINDOW_HEIGHT = int(os.getenv("WINDOW_HEIGHT", "480"))


config = Config()
