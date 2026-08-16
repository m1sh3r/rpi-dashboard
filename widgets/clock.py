import datetime
import math
from PyQt5.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QWidget

CENTER = 110.0
DIAL_HALF_SIZE = 109.0
DIAL_CORNER_RADIUS = 109.0
TICK_MAJOR_LENGTH = 20.0
TICK_MINOR_LENGTH = 10.0
EPSILON = 0.01


def get_visual_tick_length(base_length, ux, uy):
    return base_length / max(abs(ux), abs(uy), EPSILON)


def is_inside_rounded_square(x, y, half=DIAL_HALF_SIZE, radius=DIAL_CORNER_RADIUS):
    dx = abs(x - CENTER)
    dy = abs(y - CENTER)
    side = half - radius
    qx = max(dx - side, 0.0)
    qy = max(dy - side, 0.0)
    return qx * qx + qy * qy <= radius * radius + EPSILON


def get_boundary_point_by_angle(
    angle_deg, half=DIAL_HALF_SIZE, radius=DIAL_CORNER_RADIUS
):
    angle_rad = math.radians(angle_deg)
    ux = math.cos(angle_rad)
    uy = math.sin(angle_rad)
    low = 0.0
    high = half * 2.0

    for _ in range(20):
        mid = (low + high) / 2.0
        x = CENTER + ux * mid
        y = CENTER + uy * mid
        if is_inside_rounded_square(x, y, half, radius):
            low = mid
        else:
            high = mid

    return {
        "x": CENTER + ux * low,
        "y": CENTER + uy * low,
        "ux": ux,
        "uy": uy,
        "distance": low,
    }


def precompute_minute_ticks():
    ticks = []
    for idx in range(60):
        angle_deg = idx * 6.0 - 90.0
        boundary = get_boundary_point_by_angle(angle_deg)
        is_major = idx % 5 == 0
        base_length = TICK_MAJOR_LENGTH if is_major else TICK_MINOR_LENGTH
        length = get_visual_tick_length(base_length, boundary["ux"], boundary["uy"])

        ticks.append(
            {
                "idx": idx,
                "is_major": is_major,
                "x1": boundary["x"] - boundary["ux"] * length,
                "y1": boundary["y"] - boundary["uy"] * length,
                "x2": boundary["x"],
                "y2": boundary["y"],
            }
        )
    return ticks


MINUTE_TICKS = precompute_minute_ticks()


class AnalogClock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 220)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def sizeHint(self):
        return QSize(220, 220)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        side = min(w, h)
        scale = side / 220.0
        center_x = w / 2.0
        center_y = h / 2.0

        now = datetime.datetime.now()
        second = now.second + now.microsecond / 1_000_000.0
        minute = now.minute + second / 60.0
        hour = (now.hour % 12) + minute / 60.0

        second_angle = second * 6.0
        minute_angle = minute * 6.0
        hour_angle = (hour % 12) * 30.0 + (minute % 60) * 0.5

        painter.save()
        painter.translate(center_x, center_y)
        painter.scale(scale, scale)
        painter.translate(-CENTER, -CENTER)

        for tick in MINUTE_TICKS:
            is_major = tick["is_major"]
            alpha = int(255 * (0.75 if is_major else 0.50))
            width = 2.0 if is_major else 1.0
            pen = QPen(QColor(242, 242, 242, alpha), width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(
                QPointF(tick["x1"], tick["y1"]), QPointF(tick["x2"], tick["y2"])
            )

        time_str = now.strftime("%H:%M:%S")
        painter.setPen(QColor(255, 255, 255, 160))
        digi_font = QFont("Segoe UI", 8)
        digi_font.setItalic(True)
        painter.setFont(digi_font)
        painter.drawText(
            QRectF(CENTER - 60, 182 - 12, 120, 20), Qt.AlignCenter, time_str
        )

        painter.save()
        painter.translate(CENTER, CENTER)
        painter.rotate(minute_angle)
        painter.translate(-CENTER, -CENTER)
        painter.setPen(
            QPen(
                QColor(242, 242, 242),
                8.0,
                Qt.SolidLine,
                Qt.RoundCap,
            )
        )
        painter.drawLine(QPointF(CENTER, CENTER), QPointF(CENTER, 50))
        painter.setPen(
            QPen(
                QColor(255, 255, 255),
                8.0,
                Qt.SolidLine,
                Qt.RoundCap,
            )
        )
        painter.drawLine(QPointF(CENTER, CENTER), QPointF(CENTER, 10))
        painter.setPen(
            QPen(QColor(0, 0, 0), 5.0, Qt.SolidLine, Qt.RoundCap)
        )
        painter.drawLine(QPointF(CENTER, 50), QPointF(CENTER, 10))
        painter.restore()

        painter.save()
        painter.translate(CENTER, CENTER)
        painter.rotate(hour_angle)
        painter.translate(-CENTER, -CENTER)
        painter.setPen(
            QPen(
                QColor(242, 242, 242),
                8.0,
                Qt.SolidLine,
                Qt.RoundCap,
            )
        )
        painter.drawLine(QPointF(CENTER, CENTER), QPointF(CENTER, 55))
        painter.setPen(
            QPen(QColor(0, 0, 0), 5.0, Qt.SolidLine, Qt.RoundCap)
        )
        painter.drawLine(QPointF(CENTER, CENTER), QPointF(CENTER, 55))
        painter.restore()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(250, 250, 250))
        painter.drawEllipse(QPointF(CENTER, CENTER), 4.0, 4.0)

        painter.setBrush(QColor(255, 39, 39))
        painter.drawEllipse(QPointF(CENTER, CENTER), 3.5, 3.5)

        painter.save()
        painter.translate(CENTER, CENTER)
        painter.rotate(second_angle)
        painter.translate(-CENTER, -CENTER)
        painter.setPen(
            QPen(
                QColor(255, 39, 39), 2.0, Qt.SolidLine, Qt.RoundCap
            )
        )
        painter.drawLine(QPointF(CENTER, 130), QPointF(CENTER, 5))
        painter.restore()

        painter.restore()
