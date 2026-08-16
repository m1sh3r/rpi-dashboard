from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .weather_icons import get_icon_renderer


class SvgIconWidget(QWidget):
    def __init__(self, size=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.renderer = None

    def set_icon(self, icon_code: str = None, condition: str = None):
        self.renderer = get_icon_renderer(icon_code, condition)
        self.update()

    def paintEvent(self, event):
        if self.renderer and self.renderer.isValid():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            self.renderer.render(painter, QRectF(0, 0, self.width(), self.height()))


class CompactWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.icon_widget = SvgIconWidget(40, self)
        self.temp_label = QLabel("--°C", self)
        self.temp_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.cond_label = QLabel("Нет данных", self)
        self.extra_label = QLabel("", self)

        layout.addWidget(self.icon_widget)
        layout.addWidget(self.temp_label)
        layout.addWidget(self.cond_label)
        layout.addWidget(self.extra_label)
        layout.addStretch(1)

    def set_data(self, data: dict):
        fact = data.get("fact", {})
        temp = fact.get("temp", "--")
        cond_name = fact.get("condition_name", "")
        cond = fact.get("condition", "clear")
        icon_code = fact.get("icon")
        wind_speed = fact.get("wind_speed", 0)
        wind_dir = fact.get("wind_dir", "")

        self.icon_widget.set_icon(icon_code, cond)
        self.temp_label.setText(f"{temp}°C")
        self.cond_label.setText(cond_name)
        self.extra_label.setText(f"Ветер: {wind_dir} {wind_speed} м/с")

    def set_error(self, message: str):
        self.temp_label.setText("--°C")
        self.cond_label.setText(message)
        self.extra_label.setText("")


class ForecastDayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        self.day_label = QLabel("", self)
        self.day_label.setAlignment(Qt.AlignCenter)

        self.icon_widget = SvgIconWidget(40, self)

        self.temp_label = QLabel("", self)
        self.temp_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.day_label)
        layout.addWidget(self.icon_widget, 0, Qt.AlignCenter)
        layout.addWidget(self.temp_label)

    def set_day_data(self, day_name: str, min_t: int, max_t: int, condition: str, icon_code: str = None):
        self.day_label.setText(day_name)
        self.icon_widget.set_icon(icon_code, condition)
        self.temp_label.setText(f"{min_t:+}° / {max_t:+}°")

    def clear(self):
        self.day_label.setText("")
        self.temp_label.setText("")
        self.icon_widget.renderer = None
        self.icon_widget.update()


class FullWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(14)

        self.hero_layout = QHBoxLayout()
        self.hero_layout.setSpacing(16)

        self.main_icon = SvgIconWidget(90, self)
        self.hero_layout.addWidget(self.main_icon)

        text_layout = QVBoxLayout()
        self.temp_label = QLabel("--°C", self)
        self.temp_label.setStyleSheet("font-size: 42px; font-weight: bold;")
        self.cond_label = QLabel("Нет данных", self)
        self.cond_label.setStyleSheet("font-size: 18px;")
        text_layout.addWidget(self.temp_label)
        text_layout.addWidget(self.cond_label)

        self.hero_layout.addLayout(text_layout)
        self.hero_layout.addStretch(1)
        self.main_layout.addLayout(self.hero_layout)

        self.details_label = QLabel("", self)
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        self.main_layout.addWidget(self.details_label)

        self.forecast_layout = QHBoxLayout()
        self.forecast_layout.setSpacing(8)
        self.forecast_days = []
        for _ in range(5):
            day_widget = ForecastDayWidget(self)
            self.forecast_layout.addWidget(day_widget, 1)
            self.forecast_days.append(day_widget)

        self.main_layout.addLayout(self.forecast_layout)
        self.main_layout.addStretch(1)

    def set_data(self, data: dict):
        fact = data.get("fact", {})
        temp = fact.get("temp", "--")
        feels_like = fact.get("feels_like", "--")
        cond = fact.get("condition", "clear")
        cond_name = fact.get("condition_name", "")
        icon_code = fact.get("icon")
        humidity = fact.get("humidity", "--")
        pressure = fact.get("pressure_mm", "--")
        wind_speed = fact.get("wind_speed", "--")
        wind_dir = fact.get("wind_dir", "")

        self.main_icon.set_icon(icon_code, cond)
        self.temp_label.setText(f"{temp:+}°C" if isinstance(temp, (int, float)) else f"{temp}°C")
        self.cond_label.setText(f"{cond_name} (ощущается как {feels_like}°C)")
        self.details_label.setText(
            f"Влажность: {humidity}%  |  Давление: {pressure} мм рт. ст.  |  Ветер: {wind_dir} {wind_speed} м/с"
        )

        forecast = data.get("forecast", [])
        for idx, day_widget in enumerate(self.forecast_days):
            if idx < len(forecast):
                item = forecast[idx]
                day_widget.set_day_data(
                    day_name=item.get("day_name", ""),
                    min_t=item.get("min_temp", 0),
                    max_t=item.get("max_temp", 0),
                    condition=item.get("condition", "clear"),
                    icon_code=item.get("icon"),
                )
            else:
                day_widget.clear()

    def set_error(self, message: str):
        self.temp_label.setText("--°C")
        self.cond_label.setText(message)
        self.details_label.setText("")
        self.main_icon.renderer = None
        self.main_icon.update()
        for day_widget in self.forecast_days:
            day_widget.clear()


class WeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.compact = CompactWeatherWidget(self)
        self.full = FullWeatherWidget(self)

        self.layout.addWidget(self.compact)
        self.layout.addWidget(self.full)

        self.set_compact_mode(False)

    def set_compact_mode(self, is_compact: bool):
        if is_compact:
            self.full.hide()
            self.compact.show()
        else:
            self.compact.hide()
            self.full.show()

    def update_data(self, data: dict):
        self.compact.set_data(data)
        self.full.set_data(data)

    def set_error(self, message: str):
        self.compact.set_error(message)
        self.full.set_error(message)
