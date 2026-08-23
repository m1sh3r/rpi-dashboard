from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import (
    QFrame,
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
        self.icon_code = None
        self.condition = None

    def set_icon(self, icon_code: str = None, condition: str = None):
        self.icon_code = icon_code
        self.condition = condition
        self.renderer = get_icon_renderer(icon_code, condition, on_loaded=self._on_icon_loaded)
        self.update()

    def _on_icon_loaded(self):
        self.renderer = get_icon_renderer(self.icon_code, self.condition)
        self.update()

    def paintEvent(self, event):
        if self.renderer and self.renderer.isValid():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            self.renderer.render(painter, QRectF(0, 0, self.width(), self.height()))


class CompactWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignCenter)

        self.cond_label = QLabel("Нет данных", self)
        self.cond_label.setStyleSheet(
            "font-size: 36px; font-weight: 400; color: rgba(255, 255, 255, 0.85);"
        )

        self.icon_widget = SvgIconWidget(58, self)

        self.temp_label = QLabel("--°C", self)
        self.temp_label.setStyleSheet(
            "font-size: 48px; font-weight: 700; color: rgba(255, 255, 255, 0.95);"
        )

        self.feels_label = QLabel("", self)
        self.feels_label.setStyleSheet(
            "font-size: 36px; font-style: italic; font-weight: 400; color: rgba(255, 255, 255, 0.75);"
        )

        layout.addWidget(self.cond_label)
        layout.addWidget(self.icon_widget)
        layout.addWidget(self.temp_label)
        layout.addWidget(self.feels_label)

    def set_data(self, data: dict):
        fact = data.get("fact", {})
        temp = fact.get("temp", "--")
        feels_like = fact.get("feels_like", "--")
        cond_name = fact.get("condition_name", "")
        cond = fact.get("condition", "clear")
        icon_code = fact.get("icon")

        self.cond_label.setText(cond_name)
        self.icon_widget.set_icon(icon_code, cond)
        self.temp_label.setText(f"{temp}°C" if temp != "--" else "--°C")
        self.feels_label.setText(
            f"как {feels_like}°C" if feels_like != "--" else ""
        )

    def set_error(self, message: str):
        self.cond_label.setText(message)
        self.icon_widget.renderer = None
        self.icon_widget.update()
        self.temp_label.setText("--°C")
        self.feels_label.setText("")


class ForecastDayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self.day_label = QLabel("", self)
        self.day_label.setAlignment(Qt.AlignCenter)
        self.day_label.setStyleSheet(
            "font-size: 20px; font-weight: 500; color: rgba(255, 255, 255, 0.65); letter-spacing: 0.5px;"
        )

        self.icon_widget = SvgIconWidget(64, self)

        self.temp_label = QLabel("", self)
        self.temp_label.setAlignment(Qt.AlignCenter)
        self.temp_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: rgba(255, 255, 255, 0.85);"
        )

        layout.addWidget(self.day_label)
        layout.addWidget(self.icon_widget, 0, Qt.AlignCenter)
        layout.addWidget(self.temp_label)

    def set_day_data(
        self,
        day_name: str,
        min_t: int,
        max_t: int,
        condition: str,
        icon_code: str = None,
    ):
        self.day_label.setText(day_name.upper())
        self.icon_widget.set_icon(icon_code, condition)
        self.temp_label.setText(
            f'<span>{max_t}°</span> / <span style="font-weight: 400; color: rgba(255, 255, 255, 0.55);">{min_t}°</span>'
        )

    def clear(self):
        self.day_label.setText("")
        self.temp_label.setText("")
        self.icon_widget.renderer = None
        self.icon_widget.update()


class DetailItemWidget(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel(title, self)
        self.label.setStyleSheet(
            "font-size: 24px; font-weight: 500; color: rgba(255, 255, 255, 0.45); letter-spacing: 0.5px;"
        )

        self.value = QLabel("—", self)
        self.value.setStyleSheet(
            "font-size: 32px; font-weight: 600; color: rgba(255, 255, 255, 0.85);"
        )

        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, text: str):
        self.value.setText(text)


class FullWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 10, 20, 10)
        self.main_layout.setSpacing(20)
        self.main_layout.setAlignment(Qt.AlignCenter)

        self.hero_layout = QHBoxLayout()
        self.hero_layout.setSpacing(40)
        self.hero_layout.setAlignment(Qt.AlignCenter)

        self.cond_label = QLabel("Нет данных", self)
        self.cond_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cond_label.setWordWrap(True)
        self.cond_label.setStyleSheet(
            "font-size: 48px; font-weight: 400; color: rgba(255, 255, 255, 0.85); line-height: 1.2;"
        )

        self.main_icon = SvgIconWidget(180, self)

        temp_box = QVBoxLayout()
        temp_box.setSpacing(2)
        temp_box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.temp_label = QLabel("--°C", self)
        self.temp_label.setStyleSheet(
            "font-size: 80px; font-weight: 700; color: rgba(255, 255, 255, 0.95);"
        )

        self.feels_label = QLabel("", self)
        self.feels_label.setStyleSheet(
            "font-size: 32px; font-style: italic; font-weight: 400; color: rgba(255, 255, 255, 0.75);"
        )

        temp_box.addWidget(self.temp_label)
        temp_box.addWidget(self.feels_label)

        self.hero_layout.addWidget(self.cond_label, 1)
        self.hero_layout.addWidget(self.main_icon, 0, Qt.AlignCenter)
        self.hero_layout.addLayout(temp_box, 1)

        self.main_layout.addLayout(self.hero_layout)

        self.details_layout = QHBoxLayout()
        self.details_layout.setSpacing(32)
        self.details_layout.setAlignment(Qt.AlignCenter)

        self.wind_item = DetailItemWidget("ВЕТЕР", self)
        self.humidity_item = DetailItemWidget("ВЛАЖНОСТЬ", self)
        self.pressure_item = DetailItemWidget("ДАВЛЕНИЕ", self)

        self.details_layout.addWidget(self.wind_item)
        self.details_layout.addWidget(self.humidity_item)
        self.details_layout.addWidget(self.pressure_item)

        self.main_layout.addLayout(self.details_layout)

        self.forecast_frame = QFrame(self)
        self.forecast_frame.setStyleSheet(
            "border-top: 1px solid rgba(255, 255, 255, 0.10); padding-top: 14px;"
        )
        self.forecast_layout = QHBoxLayout(self.forecast_frame)
        self.forecast_layout.setContentsMargins(0, 0, 0, 0)
        self.forecast_layout.setSpacing(16)
        self.forecast_layout.setAlignment(Qt.AlignCenter)

        self.forecast_days = []
        for _ in range(5):
            day_widget = ForecastDayWidget(self.forecast_frame)
            day_widget.setStyleSheet("border: none; padding-top: 0px;")
            self.forecast_layout.addWidget(day_widget)
            self.forecast_days.append(day_widget)

        self.main_layout.addWidget(self.forecast_frame)

    def set_data(self, data: dict):
        fact = data.get("fact", {})
        temp = fact.get("temp", "--")
        feels_like = fact.get("feels_like", "--")
        cond = fact.get("condition", "clear")
        cond_name = fact.get("condition_name", "")
        icon_code = fact.get("icon")
        humidity = fact.get("humidity", 0)
        pressure = fact.get("pressure_mm", 0)
        wind_speed = fact.get("wind_speed", 0)
        wind_arrow = fact.get("wind_arrow", "")

        self.main_icon.set_icon(icon_code, cond)
        self.cond_label.setText(cond_name)
        self.temp_label.setText(f"{temp}°C" if temp != "--" else "--°C")
        self.feels_label.setText(
            f"как {feels_like}°C" if feels_like != "--" else ""
        )

        wind_str = f"{str(wind_speed).replace('.', ',')} м/с {wind_arrow}".strip()
        self.wind_item.set_value(wind_str)
        self.humidity_item.set_value(f"{humidity}%")
        self.pressure_item.set_value(f"{pressure} мм")

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
        self.cond_label.setText(message)
        self.main_icon.renderer = None
        self.main_icon.update()
        self.temp_label.setText("--°C")
        self.feels_label.setText("")
        self.wind_item.set_value("—")
        self.humidity_item.set_value("—")
        self.pressure_item.set_value("—")
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
