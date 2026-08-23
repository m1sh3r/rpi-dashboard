import os
import sys

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_FONT_DPI"] = "96"

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

import argparse
from pathlib import Path
import random
import signal

signal.signal(signal.SIGINT, signal.SIG_DFL)

from PyQt5.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation
from PyQt5.QtGui import QBrush, QColor, QFont, QFontDatabase, QKeyEvent, QPainter, QRadialGradient
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from config import config
from api import WeatherClient
from api.constants import (
    CONDITION_TO_ICON,
    YANDEX_CONDITION_NAMES,
    degree_to_wind_arrow,
    degree_to_wind_direction,
)
from widgets import (
    AnalogClock,
    CalendarWidget,
    PcStatusWidget,
    WeatherEffectsWidget,
    WeatherWidget,
    get_dashboard_rounded_path,
    get_inter_font,
    load_fonts,
)

MOCK_CONDITIONS = [
    "clear",
    "partly-cloudy",
    "cloudy",
    "overcast",
    "light-rain",
    "rain",
    "heavy-rain",
    "showers",
    "sleet",
    "light-snow",
    "snow",
    "snowfall",
    "hail",
    "thunderstorm",
    "thunderstorm-with-rain",
    "thunderstorm-with-hail",
]


class DashboardWindow(QWidget):
    def __init__(self, mock_weather: bool = False, auto_switch_sec: float = 0.0):
        super().__init__()
        self.is_pc_online = False
        self.mock_weather = mock_weather
        self.mock_index = 0

        self.setWindowTitle("RPI Dashboard")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(1920, 480)
        self.setStyleSheet("DashboardWindow { color: #ffffff; }")

        self.bg_start = QColor("#2c241c")
        self.bg_end = QColor("#1c1814")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(20)

        self.calendar = CalendarWidget(self)
        self.calendar.setFixedWidth(460)
        main_layout.addWidget(self.calendar)

        center_container = QFrame(self)
        self.center_layout = QVBoxLayout(center_container)
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(10)

        self.weather = WeatherWidget(center_container)
        self.pc_status = PcStatusWidget(center_container)

        self.center_layout.addWidget(self.weather, 1)
        self.center_layout.addWidget(self.pc_status, 1)

        main_layout.addWidget(center_container, 1)

        self.clock = AnalogClock(self)
        self.clock.setFixedWidth(460)
        main_layout.addWidget(self.clock)

        self.effects = WeatherEffectsWidget(self)
        self.effects.setGeometry(0, 0, 1920, 480)
        self.effects.raise_()

        self.set_online_state(self.is_pc_online)

        if self.mock_weather:
            self._apply_mock_condition(MOCK_CONDITIONS[0])
            self.auto_timer = QTimer(self)
            if auto_switch_sec > 0:
                self.auto_timer.setInterval(int(auto_switch_sec * 1000))
                self.auto_timer.timeout.connect(self._next_random_weather)
                self.auto_timer.start()
        else:
            self.weather_client = WeatherClient(self)
            self.weather_client.weather_updated.connect(self._on_weather_updated)
            self.weather_client.weather_error.connect(self.weather.set_error)
            cached = self.weather_client.get_cached_payload()
            if cached:
                self._on_weather_updated(cached)
            self.weather_client.update_weather()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.effects.setGeometry(self.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w = float(self.width())
        h = float(self.height())
        path = get_dashboard_rounded_path(w, h)
        grad = QRadialGradient(w * 0.5, h * 0.2, max(w, h) * 0.8, w * 0.5, h * 0.2)
        grad.setColorAt(0.0, self.bg_start)
        grad.setColorAt(1.0, self.bg_end)
        painter.fillPath(path, QBrush(grad))

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Escape, Qt.Key_Q):
            self.close()
        elif key == Qt.Key_O:
            self.set_online_state(not self.is_pc_online)
        elif self.mock_weather:
            if key in (Qt.Key_Space, Qt.Key_Right):
                self.mock_index = (self.mock_index + 1) % len(MOCK_CONDITIONS)
                self._apply_mock_condition(MOCK_CONDITIONS[self.mock_index])
            elif key == Qt.Key_Left:
                self.mock_index = (self.mock_index - 1) % len(MOCK_CONDITIONS)
                self._apply_mock_condition(MOCK_CONDITIONS[self.mock_index])
            elif key == Qt.Key_R:
                self._next_random_weather()
            elif key == Qt.Key_A and hasattr(self, "auto_timer"):
                if self.auto_timer.isActive():
                    self.auto_timer.stop()
                else:
                    self.auto_timer.start(5000)
        else:
            super().keyPressEvent(event)

    def _next_random_weather(self):
        cond = random.choice(MOCK_CONDITIONS)
        self.mock_index = MOCK_CONDITIONS.index(cond)
        self._apply_mock_condition(cond)

    def _apply_mock_condition(self, condition: str):
        is_snow = "snow" in condition or condition == "sleet"
        is_rain = "rain" in condition or condition in ["showers", "sleet", "hail"]
        temp = random.randint(-12, -2) if is_snow else (random.randint(14, 26) if condition == "clear" else random.randint(4, 17))
        feels = temp - random.randint(1, 4)
        speed = round(random.uniform(1.2, 6.5), 1)
        angle = random.randint(0, 360)
        cond_name = YANDEX_CONDITION_NAMES.get(condition, condition)
        icon_code = CONDITION_TO_ICON.get(condition, "skc_d")

        forecast = []
        for d in ["ПН", "ВТ", "СР", "ЧТ", "ПТ"]:
            fc_cond = random.choice(MOCK_CONDITIONS)
            forecast.append({
                "day_name": d,
                "min_temp": temp - random.randint(2, 5),
                "max_temp": temp + random.randint(1, 4),
                "condition": fc_cond,
                "icon": CONDITION_TO_ICON.get(fc_cond, "skc_d"),
            })

        mock_data = {
            "source": "mock",
            "fact": {
                "temp": temp,
                "feels_like": feels,
                "condition": condition,
                "condition_name": cond_name,
                "icon": icon_code,
                "wind_speed": speed,
                "wind_dir": degree_to_wind_direction(angle),
                "wind_arrow": degree_to_wind_arrow(angle),
                "wind_angle": angle,
                "pressure_mm": random.randint(745, 760),
                "humidity": random.randint(50, 95) if (is_rain or is_snow) else random.randint(35, 65),
            },
            "forecast": forecast,
        }
        self._on_weather_updated(mock_data)

    def _on_weather_updated(self, data: dict):
        self.weather.update_data(data)
        fact = data.get("fact", {})
        cond = fact.get("condition", "clear")
        speed = float(fact.get("wind_speed", 2.0))
        angle = float(fact.get("wind_angle", 270.0))
        self.effects.set_weather_params(cond, speed, angle)
        self._update_background_theme(cond)

    def _update_background_theme(self, condition: str):
        if condition in ["partly-cloudy", "cloudy", "overcast", "fog"]:
            target_start = QColor("#22282d")
            target_end = QColor("#161819")
        elif condition in ["light-rain", "rain", "heavy-rain", "showers", "sleet"]:
            target_start = QColor("#21242d")
            target_end = QColor("#131417")
        elif condition in ["light-snow", "snow", "snowfall", "hail"]:
            target_start = QColor("#242c2e")
            target_end = QColor("#171a1b")
        elif condition in ["thunderstorm", "thunderstorm-with-rain", "thunderstorm-with-hail"]:
            target_start = QColor("#251e28")
            target_end = QColor("#141116")
        else:
            target_start = QColor("#2c241c")
            target_end = QColor("#1c1814")

        if self.bg_start == target_start and self.bg_end == target_end:
            return

        if hasattr(self, "bg_anim") and self.bg_anim and self.bg_anim.state() == QVariantAnimation.Running:
            self.bg_anim.stop()

        start_c1, end_c1 = self.bg_start, target_start
        start_c2, end_c2 = self.bg_end, target_end

        self.bg_anim = QVariantAnimation(self)
        self.bg_anim.setDuration(1200)
        self.bg_anim.setStartValue(0.0)
        self.bg_anim.setEndValue(1.0)
        
        bezier_curve = QEasingCurve(QEasingCurve.BezierSpline)
        bezier_curve.addCubicBezierSegment(QPointF(0.075, 0.82), QPointF(0.165, 1.0), QPointF(1.0, 1.0))
        self.bg_anim.setEasingCurve(bezier_curve)

        def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
            r = int(c1.red() + (c2.red() - c1.red()) * t)
            g = int(c1.green() + (c2.green() - c1.green()) * t)
            b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
            return QColor(r, g, b)

        def _on_step(val):
            t = float(val)
            self.bg_start = _lerp_color(start_c1, end_c1, t)
            self.bg_end = _lerp_color(start_c2, end_c2, t)
            self.update()

        self.bg_anim.valueChanged.connect(_on_step)
        self.bg_anim.start()

    def set_online_state(self, is_online: bool):
        self.is_pc_online = is_online
        if is_online:
            self.weather.set_compact_mode(True)
            self.pc_status.show()
        else:
            self.weather.set_compact_mode(False)
            self.pc_status.hide()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock-weather", action="store_true")
    parser.add_argument("--auto-switch", type=float, default=0.0)
    args, _ = parser.parse_known_args()

    if hasattr(Qt, "AA_DisableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
    if hasattr(Qt, "AA_Use96Dpi"):
        QApplication.setAttribute(Qt.AA_Use96Dpi, True)

    app = QApplication(sys.argv)
    load_fonts()
    app.setFont(get_inter_font(12, weight=400))
    if not args.mock_weather:
        app.setOverrideCursor(Qt.BlankCursor)
    window = DashboardWindow(
        mock_weather=args.mock_weather,
        auto_switch_sec=args.auto_switch,
    )
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
