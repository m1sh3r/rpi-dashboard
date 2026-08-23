import math
from PyQt5.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
)
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QPainter
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from api.constants import CONDITION_TO_ICON
from .fonts import get_inter_font
from .weather_icons import get_icon_renderer


def create_custom_bezier_curve() -> QEasingCurve:
    curve = QEasingCurve(QEasingCurve.BezierSpline)
    curve.addCubicBezierSegment(QPointF(0.075, 0.82), QPointF(0.165, 1.0), QPointF(1.0, 1.0))
    return curve


CUSTOM_BEZIER = create_custom_bezier_curve()


NON_BREAKING_PREPOSITIONS = {
    "с", "со", "в", "во", "на", "по", "к", "ко", "о", "об", "обо",
    "от", "ото", "до", "из", "изо", "за", "у", "без", "безо",
    "над", "под", "при", "про", "и", "а", "но", "да", "или", "не",
}


class AnimatedLabel(QWidget):
    def __init__(
        self,
        text: str = "",
        font_size: int = 24,
        font_weight: int = 400,
        italic: bool = False,
        color: QColor = QColor(255, 255, 255, 220),
        alignment: Qt.Alignment = Qt.AlignLeft | Qt.AlignVCenter,
        word_wrap: bool = False,
        parent: QWidget = None,
    ):
        super().__init__(parent)
        self._text = text
        self._old_text = ""
        self._font_size = font_size
        self._font_weight = font_weight
        self._italic = italic
        self._color = color
        self._alignment = alignment
        self._word_wrap = word_wrap
        self._progress = 1.0

        f = get_inter_font(
            size=font_size,
            weight=font_weight,
            italic=italic,
            is_pixel_size=True,
        )
        self.setFont(f)

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(600)
        self.anim.setEasingCurve(QEasingCurve.Linear)
        self.anim.valueChanged.connect(self._on_anim_step)

    def _on_anim_step(self, val):
        self._progress = float(val)
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def setText(self, new_text: str):
        if self._text == new_text:
            return
        self._old_text = self._text
        self._text = new_text
        if not self._old_text or self._old_text in ["--°C", "Нет данных", "—", "", "--"]:
            self._progress = 1.0
            self.updateGeometry()
            self.update()
            return
        if self.anim.state() == QVariantAnimation.Running:
            self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def clear(self):
        self.setText("")

    def _layout_lines(self, txt: str, max_w: float):
        if not txt:
            return []
        fm = QFontMetricsF(self.font())
        if not self._word_wrap or max_w <= 0:
            return [txt]
        raw_words = txt.strip().split()
        grouped_tokens = []
        i = 0
        while i < len(raw_words):
            word = raw_words[i]
            if word.lower() in NON_BREAKING_PREPOSITIONS and i + 1 < len(raw_words):
                grouped_tokens.append(word + " " + raw_words[i + 1])
                i += 2
            else:
                grouped_tokens.append(word)
                i += 1

        lines = []
        cur_line = []
        for token in grouped_tokens:
            test_line = " ".join(cur_line + [token])
            if cur_line and fm.horizontalAdvance(test_line) > max_w:
                lines.append(" ".join(cur_line))
                cur_line = [token]
            else:
                cur_line.append(token)
        if cur_line:
            lines.append(" ".join(cur_line))
        return lines

    def _get_text_bounds(self, txt: str):
        if not txt:
            return 0.0, 0.0
        fm = QFontMetricsF(self.font())
        lines = self._layout_lines(txt, 340.0 if self._word_wrap else 0.0)
        if not lines:
            return 0.0, 0.0
        w = max(fm.horizontalAdvance(line) for line in lines)
        h = len(lines) * fm.lineSpacing()
        return w, h

    def sizeHint(self) -> QSize:
        fm = QFontMetricsF(self.font())
        old_w, old_h = self._get_text_bounds(self._old_text)
        new_w, new_h = self._get_text_bounds(self._text)
        if self._progress >= 1.0 or not self._old_text:
            w, h = new_w, new_h
        else:
            e_w = CUSTOM_BEZIER.valueForProgress(self._progress)
            w = old_w + (new_w - old_w) * e_w
            h = old_h + (new_h - old_h) * e_w
        return QSize(int(math.ceil(w)), int(math.ceil(max(h, fm.height()))))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setClipRect(self.rect())
        painter.setFont(self.font())

        fm = QFontMetricsF(self.font())
        w = float(self.width())
        h = float(self.height())
        line_h = fm.lineSpacing()

        t = self._progress
        wrap_width = 340.0 if self._word_wrap else 0.0

        if t >= 1.0:
            painter.setPen(self._color)
            lines = self._layout_lines(self._text, wrap_width)
            total_h = len(lines) * line_h
            start_y = (h - total_h) / 2.0 + fm.ascent()
            for row_idx, line in enumerate(lines):
                line_w = fm.horizontalAdvance(line)
                if self._alignment & Qt.AlignRight:
                    lx = w - line_w
                elif self._alignment & Qt.AlignCenter or self._alignment & Qt.AlignHCenter:
                    lx = (w - line_w) / 2.0
                else:
                    lx = 0.0
                painter.drawText(QPointF(lx, start_y + row_idx * line_h), line)
            return

        t_old = min(1.0, t / 0.35)
        op_old = max(0.0, 1.0 - math.sin(t_old * (math.pi / 2.0)))
        if op_old > 0.005 and self._old_text:
            lines_old = self._layout_lines(self._old_text, wrap_width)
            total_h_old = len(lines_old) * line_h
            start_y_old = (h - total_h_old) / 2.0 + fm.ascent()
            scale_old = 1.0 + 0.04 * t_old
            c_old = QColor(self._color)
            c_old.setAlpha(int(self._color.alpha() * op_old))

            for row_idx, line in enumerate(lines_old):
                line_w = fm.horizontalAdvance(line)
                if self._alignment & Qt.AlignRight:
                    lx = w - line_w
                elif self._alignment & Qt.AlignCenter or self._alignment & Qt.AlignHCenter:
                    lx = (w - line_w) / 2.0
                else:
                    lx = 0.0

                center_x = lx + line_w / 2.0
                center_y = start_y_old + row_idx * line_h - fm.ascent() / 2.0

                painter.save()
                painter.translate(center_x, center_y)
                painter.scale(scale_old, scale_old)
                painter.translate(-center_x, -center_y)
                painter.setPen(c_old)
                painter.drawText(QPointF(lx, start_y_old + row_idx * line_h), line)
                painter.restore()

        lines_new = self._layout_lines(self._text, wrap_width)
        total_h_new = len(lines_new) * line_h
        start_y_new = (h - total_h_new) / 2.0 + fm.ascent()

        total_chars = max(len(self._text), 1)
        stagger = 0.25
        duration = 1.0 - stagger

        char_counter = 0
        for row_idx, line in enumerate(lines_new):
            line_w = fm.horizontalAdvance(line)
            if self._alignment & Qt.AlignRight:
                cur_x = w - line_w
            elif self._alignment & Qt.AlignCenter or self._alignment & Qt.AlignHCenter:
                cur_x = (w - line_w) / 2.0
            else:
                cur_x = 0.0

            baseline_y = start_y_new + row_idx * line_h

            for ch in line:
                ch_w = fm.horizontalAdvance(ch)
                delay = (char_counter / max(total_chars - 1, 1)) * stagger if total_chars > 1 else 0.0
                char_t = max(0.0, min(1.0, (t - delay) / duration))

                if char_t > 0.0:
                    e_t = CUSTOM_BEZIER.valueForProgress(char_t) if char_t < 1.0 else 1.0
                    scale_ch = 0.50 + 0.50 * e_t
                    op_ch = min(1.0, math.sin(min(1.0, char_t * 1.35) * (math.pi / 2.0)))

                    ch_center_x = cur_x + ch_w / 2.0
                    ch_center_y = baseline_y - fm.ascent() / 2.0

                    c_new = QColor(self._color)
                    c_new.setAlpha(int(self._color.alpha() * op_ch))

                    painter.save()
                    painter.translate(ch_center_x, ch_center_y)
                    painter.scale(scale_ch, scale_ch)
                    painter.translate(-ch_center_x, -ch_center_y)
                    painter.setPen(c_new)
                    painter.drawText(QPointF(cur_x, baseline_y), ch)
                    painter.restore()

                cur_x += ch_w
                char_counter += 1


class SvgIconWidget(QWidget):
    def __init__(self, size=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.renderer = None
        self.old_renderer = None
        self.icon_code = None
        self.condition = None
        self._current_code = None
        self._progress = 1.0

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(600)
        self.anim.setEasingCurve(QEasingCurve.Linear)
        self.anim.valueChanged.connect(self._on_anim_step)

    def _on_anim_step(self, val):
        self._progress = float(val)
        self.update()

    def set_icon(self, icon_code: str = None, condition: str = None):
        code = icon_code or CONDITION_TO_ICON.get(condition, "skc_d") or "skc_d"
        self.icon_code = icon_code
        self.condition = condition
        self._current_code = code
        self.renderer = get_icon_renderer(icon_code, condition, on_loaded=self._on_icon_loaded)
        self.old_renderer = None
        self._progress = 1.0
        self.update()

    def update_icon(self, icon_code: str = None, condition: str = None):
        code = icon_code or CONDITION_TO_ICON.get(condition, "skc_d") or "skc_d"
        if self._current_code == code and self.renderer is not None:
            self.icon_code = icon_code
            self.condition = condition
            return
        if self.renderer is None or self._current_code is None:
            self.set_icon(icon_code, condition)
            return

        self.old_renderer = self.renderer
        self.icon_code = icon_code
        self.condition = condition
        self._current_code = code
        self.renderer = get_icon_renderer(icon_code, condition, on_loaded=self._on_icon_loaded)

        if self.renderer is None:
            return

        if self.renderer == self.old_renderer:
            self.old_renderer = None
            self._progress = 1.0
            self.update()
            return

        if self.anim.state() == QVariantAnimation.Running:
            self.anim.stop()
        self._progress = 0.0
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _on_icon_loaded(self):
        new_renderer = get_icon_renderer(self.icon_code, self.condition)
        if new_renderer and new_renderer.isValid():
            if self.old_renderer and self.old_renderer != new_renderer:
                self.renderer = new_renderer
                if self.anim.state() == QVariantAnimation.Running:
                    self.anim.stop()
                self._progress = 0.0
                self.anim.setStartValue(0.0)
                self.anim.setEndValue(1.0)
                self.anim.start()
            else:
                self.renderer = new_renderer
                self.old_renderer = None
                self._progress = 1.0
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipRect(self.rect())
        w = float(self.width())
        h = float(self.height())
        center_x = w / 2.0
        center_y = h / 2.0
        target_rect = QRectF(0, 0, w, h)

        t = self._progress

        if t >= 1.0:
            if self.renderer and self.renderer.isValid():
                self.renderer.render(painter, target_rect)
            return

        t_old = min(1.0, t / 0.40)
        op_old = max(0.0, 1.0 - math.sin(t_old * (math.pi / 2.0)))
        if op_old > 0.005 and self.old_renderer and self.old_renderer.isValid():
            scale_old = 1.0 + 0.15 * t_old
            painter.save()
            painter.setOpacity(op_old)
            painter.translate(center_x, center_y)
            painter.scale(scale_old, scale_old)
            painter.translate(-center_x, -center_y)
            self.old_renderer.render(painter, target_rect)
            painter.restore()

        if self.renderer and self.renderer.isValid():
            e_t = CUSTOM_BEZIER.valueForProgress(t) if t < 1.0 else 1.0
            scale_new = 0.50 + 0.50 * e_t
            op_new = min(1.0, math.sin(min(1.0, t * 1.35) * (math.pi / 2.0)))

            painter.save()
            painter.setOpacity(op_new)
            painter.translate(center_x, center_y)
            painter.scale(scale_new, scale_new)
            painter.translate(-center_x, -center_y)
            self.renderer.render(painter, target_rect)
            painter.restore()


class CompactWeatherWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignCenter)

        self.cond_label = AnimatedLabel(
            "Нет данных",
            font_size=36,
            font_weight=400,
            color=QColor(255, 255, 255, int(255 * 0.85)),
            parent=self,
        )

        self.icon_widget = SvgIconWidget(58, self)

        self.temp_label = AnimatedLabel(
            "--°C",
            font_size=48,
            font_weight=700,
            color=QColor(255, 255, 255, int(255 * 0.95)),
            parent=self,
        )

        self.feels_label = AnimatedLabel(
            "",
            font_size=36,
            font_weight=400,
            italic=True,
            color=QColor(255, 255, 255, int(255 * 0.75)),
            parent=self,
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
        self.icon_widget.update_icon(icon_code, cond)
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
        self.setFixedWidth(130)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        self.day_label = AnimatedLabel(
            "",
            font_size=20,
            font_weight=500,
            color=QColor(255, 255, 255, int(255 * 0.65)),
            alignment=Qt.AlignCenter,
            parent=self,
        )

        self.icon_widget = SvgIconWidget(64, self)

        temp_container = QWidget(self)
        temp_layout = QHBoxLayout(temp_container)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(4)
        temp_layout.setAlignment(Qt.AlignCenter)

        self.max_temp_label = AnimatedLabel(
            "",
            font_size=24,
            font_weight=600,
            color=QColor(255, 255, 255, int(255 * 0.85)),
            alignment=Qt.AlignCenter,
            parent=temp_container,
        )

        self.slash_label = QLabel("/", temp_container)
        self.slash_label.setFont(get_inter_font(20, weight=400, is_pixel_size=True))
        self.slash_label.setStyleSheet("color: rgba(255, 255, 255, 0.35);")

        self.min_temp_label = AnimatedLabel(
            "",
            font_size=22,
            font_weight=400,
            color=QColor(255, 255, 255, int(255 * 0.55)),
            alignment=Qt.AlignCenter,
            parent=temp_container,
        )

        temp_layout.addWidget(self.max_temp_label)
        temp_layout.addWidget(self.slash_label)
        temp_layout.addWidget(self.min_temp_label)

        layout.addWidget(self.day_label)
        layout.addWidget(self.icon_widget, 0, Qt.AlignCenter)
        layout.addWidget(temp_container)

    def set_day_data(
        self,
        day_name: str,
        min_t: int,
        max_t: int,
        condition: str,
        icon_code: str = None,
    ):
        self.day_label.setText(day_name.upper())
        self.icon_widget.update_icon(icon_code, condition)
        self.max_temp_label.setText(f"{max_t}°")
        self.min_temp_label.setText(f"{min_t}°")
        self.slash_label.show()

    def clear(self):
        self.day_label.clear()
        self.max_temp_label.clear()
        self.min_temp_label.clear()
        self.slash_label.hide()
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
        self.label.setFont(get_inter_font(24, weight=500, is_pixel_size=True))
        self.label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.45); letter-spacing: 0.5px;"
        )

        self.value = AnimatedLabel(
            "—",
            font_size=32,
            font_weight=600,
            color=QColor(255, 255, 255, int(255 * 0.85)),
            parent=self,
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

        self.cond_label = AnimatedLabel(
            "Нет данных",
            font_size=48,
            font_weight=400,
            color=QColor(255, 255, 255, int(255 * 0.85)),
            alignment=Qt.AlignRight | Qt.AlignVCenter,
            word_wrap=True,
            parent=self,
        )

        self.main_icon = SvgIconWidget(180, self)

        temp_box = QVBoxLayout()
        temp_box.setSpacing(2)
        temp_box.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.temp_label = AnimatedLabel(
            "--°C",
            font_size=80,
            font_weight=700,
            color=QColor(255, 255, 255, int(255 * 0.95)),
            parent=self,
        )

        self.feels_label = AnimatedLabel(
            "",
            font_size=32,
            font_weight=400,
            italic=True,
            color=QColor(255, 255, 255, int(255 * 0.75)),
            parent=self,
        )

        temp_box.addWidget(self.temp_label)
        temp_box.addWidget(self.feels_label)

        self.hero_layout.addStretch(1)
        self.hero_layout.addWidget(self.cond_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.hero_layout.addWidget(self.main_icon, 0, Qt.AlignCenter)
        self.hero_layout.addLayout(temp_box, 0)
        self.hero_layout.addStretch(1)

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
        self.forecast_layout.setSpacing(0)

        self.forecast_days = []
        for i in range(5):
            if i > 0:
                self.forecast_layout.addStretch(1)
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

        self.main_icon.update_icon(icon_code, cond)
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
