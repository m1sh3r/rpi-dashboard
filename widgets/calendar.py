import calendar
import datetime
from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

RUSSIAN_MONTHS = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

RUSSIAN_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class CalendarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_date = datetime.date.today()
        self.weather_text_color = QColor(255, 255, 255, 220)
        self.setMinimumSize(320, 220)

        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self._check_date_change)
        self.timer.start()

    def sizeHint(self):
        return QSize(350, 240)

    def _check_date_change(self):
        today = datetime.date.today()
        if today != self.current_date:
            self.current_date = today
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        today = datetime.date.today()
        year = today.year
        month = today.month

        month_name = RUSSIAN_MONTHS[month]
        header_text = f"{month_name} {year}"

        body_y = 56.0
        body_h = h - body_y - 4.0
        weekdays_h = 52.0
        days_h = body_h - weekdays_h
        r = 16.0

        header_font = QFont("Segoe UI", 26, QFont.Bold)
        header_font.setItalic(True)
        painter.setFont(header_font)
        header_color = QColor(self.weather_text_color)
        header_color.setAlpha(int(255 * 0.85))
        painter.setPen(header_color)
        painter.drawText(
            QRectF(0.0, 0.0, w - 12.0, body_y),
            Qt.AlignRight | Qt.AlignVCenter,
            header_text,
        )

        border_pen = QPen(QColor(255, 255, 255, 20), 1.0)
        weekend_border_pen = QPen(QColor(239, 68, 68, 38), 1.0)

        weekdays_path = QPainterPath()
        weekdays_path.moveTo(0.0, body_y + weekdays_h)
        weekdays_path.lineTo(0.0, body_y + r)
        weekdays_path.arcTo(QRectF(0.0, body_y, r * 2, r * 2), 180.0, -90.0)
        weekdays_path.lineTo(w - r, body_y)
        weekdays_path.arcTo(QRectF(w - r * 2, body_y, r * 2, r * 2), 90.0, -90.0)
        weekdays_path.lineTo(w, body_y + weekdays_h)
        weekdays_path.closeSubpath()

        painter.save()
        painter.setClipPath(weekdays_path)

        weekday_bg = QColor(31, 31, 31, 230)
        painter.setPen(Qt.NoPen)
        painter.setBrush(weekday_bg)
        painter.drawRect(QRectF(0.0, body_y, w, weekdays_h))

        col_w = w / 7.0
        weekday_font = QFont("Segoe UI", 22, QFont.Bold)
        painter.setFont(weekday_font)

        for i, wd in enumerate(RUSSIAN_WEEKDAYS):
            is_weekend = i >= 5
            x = i * col_w
            cell_rect = QRectF(x, body_y, col_w, weekdays_h)

            if is_weekend:
                painter.fillRect(cell_rect, QColor(239, 68, 68, 10))
                painter.setPen(QColor(239, 68, 68))
            else:
                painter.setPen(QColor(255, 255, 255, 153))

            painter.drawText(cell_rect, Qt.AlignCenter, wd)

            if i < 6:
                painter.setPen(
                    weekend_border_pen if (is_weekend or i == 4) else border_pen
                )
                painter.drawLine(
                    QPointF(x + col_w, body_y), QPointF(x + col_w, body_y + weekdays_h)
                )

        painter.setPen(border_pen)
        painter.drawLine(
            QPointF(0.0, body_y + weekdays_h), QPointF(w, body_y + weekdays_h)
        )
        painter.restore()

        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(weekdays_path)

        days_y = body_y + weekdays_h
        days_path = QPainterPath()
        days_path.moveTo(0.0, days_y)
        days_path.lineTo(w, days_y)
        days_path.lineTo(w, days_y + days_h - r)
        days_path.arcTo(
            QRectF(w - r * 2, days_y + days_h - r * 2, r * 2, r * 2), 0.0, -90.0
        )
        days_path.lineTo(r, days_y + days_h)
        days_path.arcTo(
            QRectF(0.0, days_y + days_h - r * 2, r * 2, r * 2), 270.0, -90.0
        )
        days_path.lineTo(0.0, days_y)
        days_path.closeSubpath()

        painter.save()
        painter.setClipPath(days_path)

        days_bg = QColor(31, 31, 31, 224)
        painter.setPen(Qt.NoPen)
        painter.setBrush(days_bg)
        painter.drawRect(QRectF(0.0, days_y, w, days_h))

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdatescalendar(year, month)
        row_count = max(len(month_days), 6)
        row_h = days_h / float(row_count)

        day_font_normal = QFont("Segoe UI", 24)
        day_font_bold = QFont("Segoe UI", 24, QFont.Bold)
        day_font_light = QFont("Segoe UI", 22)

        for row_idx in range(row_count):
            week = month_days[row_idx] if row_idx < len(month_days) else []
            for col_idx in range(7):
                if col_idx < len(week):
                    d = week[col_idx]
                else:
                    d = datetime.date(year, month, 1)

                is_today = d == today and col_idx < len(week)
                is_curr_month = d.month == month and col_idx < len(week)
                is_weekend = col_idx >= 5

                x = col_idx * col_w
                y = days_y + row_idx * row_h
                cell_rect = QRectF(x, y, col_w, row_h)

                if is_today:
                    painter.fillRect(cell_rect, QColor(239, 68, 68))
                    painter.setPen(QColor(255, 255, 255))
                    painter.setFont(day_font_bold)
                    painter.drawText(cell_rect, Qt.AlignCenter, str(d.day))
                else:
                    if is_weekend:
                        painter.fillRect(cell_rect, QColor(239, 68, 68, 10))

                    if is_curr_month:
                        painter.setFont(day_font_normal)
                        if is_weekend:
                            painter.setPen(QColor(239, 68, 68))
                        else:
                            painter.setPen(QColor(255, 255, 255, 220))
                    else:
                        painter.setFont(day_font_light)
                        if is_weekend:
                            painter.setPen(QColor(239, 68, 68, 102))
                        else:
                            painter.setPen(QColor(90, 90, 90))

                    painter.drawText(cell_rect, Qt.AlignCenter, str(d.day))

                if col_idx < 6:
                    painter.setPen(
                        weekend_border_pen
                        if (is_weekend or col_idx == 4)
                        else border_pen
                    )
                    painter.drawLine(
                        QPointF(x + col_w, y), QPointF(x + col_w, y + row_h)
                    )

                if row_idx < row_count - 1:
                    painter.setPen(border_pen)
                    painter.drawLine(
                        QPointF(x, y + row_h), QPointF(x + col_w, y + row_h)
                    )

        painter.restore()

        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(days_path)
