import math
import random
import time
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt5.QtWidgets import QWidget


def get_dashboard_rounded_path(w: float, h: float, r_left: float = 36.0, r_right: float = 240.0) -> QPainterPath:
    r_tl = min(r_left, w / 2.0, h / 2.0)
    r_bl = min(r_left, w / 2.0, h / 2.0)
    r_tr = min(r_right, w / 2.0, h / 2.0)
    r_br = min(r_right, w / 2.0, h / 2.0)

    path = QPainterPath()
    path.moveTo(r_tl, 0)
    path.lineTo(w - r_tr, 0)
    path.arcTo(w - 2 * r_tr, 0, 2 * r_tr, 2 * r_tr, 90, -90)
    path.lineTo(w, h - r_br)
    path.arcTo(w - 2 * r_br, h - 2 * r_br, 2 * r_br, 2 * r_br, 0, -90)
    path.lineTo(r_bl, h)
    path.arcTo(0, h - 2 * r_bl, 2 * r_bl, 2 * r_bl, 270, -90)
    path.lineTo(0, r_tl)
    path.arcTo(0, 0, 2 * r_tl, 2 * r_tl, 180, -90)
    path.closeSubpath()
    return path

RAIN_CONFIG = {
    "layers": [
        {"count": 35, "speed_min": 3.5, "speed_max": 5.5, "len_min": 10, "len_max": 16, "op_min": 0.08, "op_max": 0.18, "width": 0.8},
        {"count": 45, "speed_min": 7.0, "speed_max": 10.0, "len_min": 20, "len_max": 28, "op_min": 0.18, "op_max": 0.32, "width": 1.2},
        {"count": 18, "speed_min": 12.0, "speed_max": 16.0, "len_min": 38, "len_max": 48, "op_min": 0.35, "op_max": 0.55, "width": 2.0},
    ],
    "wind": 1.8,
}

SNOW_CONFIG = {
    "layers": [
        {"count": 25, "speed_min": 0.15, "speed_max": 0.35, "rad_min": 0.8, "rad_max": 1.8, "op_min": 0.12, "op_max": 0.28},
        {"count": 35, "speed_min": 0.45, "speed_max": 0.75, "rad_min": 1.8, "rad_max": 3.2, "op_min": 0.25, "op_max": 0.45},
        {"count": 12, "speed_min": 0.9, "speed_max": 1.35, "rad_min": 3.5, "rad_max": 5.5, "op_min": 0.45, "op_max": 0.65},
    ]
}

CLOUD_CONFIG = {
    "count": 5,
    "speed_min": 0.02,
    "speed_max": 0.08,
    "rad_min": 280,
    "rad_max": 460,
    "op_min": 0.04,
    "op_max": 0.10,
}



class WeatherEffectsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.condition = "clear"
        self.wind_speed = 2.0
        self.wind_angle = 270.0

        self.particles = []
        self.splashes = []
        self.lightnings = []
        self.next_lightning_time = 0.0
        self.flash_intensity = 0.0

        self.last_time = time.time()
        self.w = 1920.0
        self.h = 480.0

        self.cloud_pixmap = self._create_cloud_texture(256)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self._recreate_particles()

    def _create_cloud_texture(self, size: int):
        from PyQt5.QtGui import QPixmap
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing, True)
        half = size / 2.0
        grad = QRadialGradient(half, half, half)
        grad.setColorAt(0.0, QColor(180, 195, 215, 200))
        grad.setColorAt(0.5, QColor(150, 165, 185, 90))
        grad.setColorAt(1.0, QColor(150, 165, 185, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(0, 0, size, size)
        p.end()
        return pix

    def set_weather_params(self, condition: str, wind_speed: float = 2.0, wind_angle: float = 270.0):
        if condition != self.condition or abs(wind_speed - self.wind_speed) > 0.5:
            self.condition = condition or "clear"
            self.wind_speed = float(wind_speed)
            self.wind_angle = float(wind_angle)
            self._recreate_particles()

    def _recreate_particles(self):
        for p in self.particles:
            p["dying"] = True
            p["target_opacity"] = 0.0

        is_rainy = self.condition in ["light-rain", "rain", "heavy-rain", "showers", "sleet", "thunderstorm-with-rain"]
        is_snowy = self.condition in ["light-snow", "snow", "snowfall", "sleet"]
        is_hailing = self.condition in ["hail", "thunderstorm-with-hail"]
        is_thundering = self.condition in ["thunderstorm", "thunderstorm-with-rain", "thunderstorm-with-hail"]
        is_cloudy = self.condition in ["partly-cloudy", "cloudy", "overcast", "fog"]

        rad = math.radians(self.wind_angle)
        wind_vx = -self.wind_speed * math.sin(rad)
        wind = wind_vx * 0.2

        new_particles = []

        if is_rainy:
            count_mult = 1.0
            speed_mult = 1.0
            len_mult = 1.0
            op_mult = 1.0
            w_mult = 1.0

            if self.condition == "light-rain":
                count_mult, speed_mult, len_mult, op_mult, w_mult = 0.6, 0.8, 0.75, 0.8, 0.8
            elif self.condition in ["heavy-rain", "thunderstorm-with-rain"]:
                count_mult, speed_mult, len_mult, op_mult, w_mult = 1.8, 1.3, 1.4, 1.2, 1.2
            elif self.condition == "showers":
                count_mult, speed_mult, len_mult, op_mult, w_mult = 2.5, 1.5, 1.6, 1.3, 1.3
            elif self.condition == "sleet":
                count_mult, speed_mult, len_mult, op_mult, w_mult = 0.4, 0.75, 0.7, 0.8, 0.8

            for layer_idx, layer in enumerate(RAIN_CONFIG["layers"]):
                cnt = int(layer["count"] * count_mult * (self.w / 1200.0))
                for _ in range(cnt):
                    vy = (random.uniform(layer["speed_min"], layer["speed_max"])) * speed_mult
                    vx = wind * (1.5 - layer_idx * 0.3) * speed_mult
                    length = random.uniform(layer["len_min"], layer["len_max"]) * len_mult
                    v_mag = max(math.sqrt(vx * vx + vy * vy), 0.001)
                    dx = (vx / v_mag) * length
                    dy = (vy / v_mag) * length
                    target_op = max(0.04, min(random.uniform(layer["op_min"], layer["op_max"]) * op_mult, 0.9))

                    new_particles.append({
                        "type": "rain",
                        "x": random.uniform(-100, self.w + 100),
                        "y": random.uniform(0, self.h),
                        "vx": vx,
                        "vy": vy,
                        "dx": dx,
                        "dy": dy,
                        "length": length,
                        "opacity": 0.0,
                        "target_opacity": target_op,
                        "dying": False,
                        "width": layer["width"] * w_mult,
                    })

        if is_snowy:
            count_mult = 1.0
            speed_mult = 1.0
            rad_mult = 1.0
            op_mult = 1.0

            if self.condition == "light-snow":
                count_mult, speed_mult, rad_mult, op_mult = 0.4, 0.7, 0.8, 0.7
            elif self.condition == "snowfall":
                count_mult, speed_mult, rad_mult, op_mult = 1.8, 1.25, 1.2, 1.15
            elif self.condition == "sleet":
                count_mult, speed_mult, rad_mult, op_mult = 0.55, 1.1, 0.9, 0.85

            for layer_idx, layer in enumerate(SNOW_CONFIG["layers"]):
                cnt = int(layer["count"] * count_mult * (self.w / 1200.0))
                for _ in range(cnt):
                    vy = random.uniform(layer["speed_min"], layer["speed_max"]) * speed_mult
                    vx = wind_vx * 0.25 * (1.3 - layer_idx * 0.2) * speed_mult
                    target_op = max(0.04, min(random.uniform(layer["op_min"], layer["op_max"]) * op_mult, 0.9))

                    new_particles.append({
                        "type": "snow",
                        "x": random.uniform(0, self.w),
                        "y": random.uniform(0, self.h),
                        "vx": vx,
                        "vy": vy,
                        "radius": random.uniform(layer["rad_min"], layer["rad_max"]) * rad_mult,
                        "opacity": 0.0,
                        "target_opacity": target_op,
                        "dying": False,
                        "swing_speed": random.uniform(0.005, 0.02),
                        "swing_range": random.uniform(5, 20),
                        "swing_offset": random.uniform(0, 100),
                    })

        if is_hailing:
            cnt = int(25 * (self.w / 1200.0))
            for _ in range(cnt):
                new_particles.append({
                    "type": "hail",
                    "x": random.uniform(-50, self.w + 50),
                    "y": random.uniform(0, self.h),
                    "speed_y": random.uniform(8.0, 16.0),
                    "speed_x": wind_vx * 0.1 + random.uniform(-0.25, 0.25),
                    "radius": random.uniform(1.5, 4.0),
                    "opacity": 0.0,
                    "target_opacity": random.uniform(0.4, 0.8),
                    "dying": False,
                })

        if is_thundering:
            self.next_lightning_time = time.time() + random.uniform(2.0, 5.0)

        if is_cloudy:
            cnt = 7 if self.condition == "overcast" else (4 if self.condition == "cloudy" else 2)
            op_mult = 1.5 if self.condition == "overcast" else 1.0
            for _ in range(max(cnt, 2)):
                target_op = min(random.uniform(CLOUD_CONFIG["op_min"], CLOUD_CONFIG["op_max"]) * op_mult, 0.25)
                new_particles.append({
                    "type": "cloud",
                    "x": random.uniform(-300, self.w + 300),
                    "y": random.uniform(0, self.h * 0.7),
                    "radius": random.uniform(CLOUD_CONFIG["rad_min"], CLOUD_CONFIG["rad_max"]),
                    "speed": random.uniform(CLOUD_CONFIG["speed_min"], CLOUD_CONFIG["speed_max"]),
                    "opacity": 0.0,
                    "target_opacity": target_op,
                    "dying": False,
                    "phase": random.uniform(0, math.pi * 2),
                    "phase_speed": random.uniform(0.0002, 0.0006),
                })


        self.particles.extend(new_particles)

    def _create_splash(self, x: float, y: float, color: QColor):
        for _ in range(random.randint(2, 4)):
            self.splashes.append({
                "x": x,
                "y": y,
                "vx": random.uniform(-1.5, 1.5),
                "vy": -random.uniform(1.0, 3.5),
                "life": 1.0,
                "decay": random.uniform(0.04, 0.10),
                "size": random.uniform(0.6, 1.8),
                "color": color,
            })

    def _create_lightning_bolt(self):
        start_x = random.uniform(0, self.w)
        segments = []
        cur_x = start_x
        cur_y = 0.0
        seg_count = random.randint(9, 17)

        for i in range(seg_count):
            next_y = cur_y + (self.h / seg_count) * random.uniform(0.8, 1.3)
            next_x = cur_x + random.uniform(-28, 28)
            segments.append((cur_x, cur_y, next_x, next_y, False))

            if random.random() < 0.20 and i < seg_count - 2:
                branch_x = next_x
                branch_y = next_y
                for _ in range(random.randint(2, 4)):
                    by = branch_y + 18
                    bx = branch_x + random.uniform(-20, 20)
                    segments.append((branch_x, branch_y, bx, by, True))
                    branch_x, branch_y = bx, by

            cur_x, cur_y = next_x, next_y
            if cur_y >= self.h:
                break

        return {
            "segments": segments,
            "opacity": 1.0,
            "decay": random.uniform(0.06, 0.14),
            "width": random.uniform(1.2, 2.5),
        }

    def _on_tick(self):
        now = time.time()
        delta = now - self.last_time
        self.last_time = now

        if delta <= 0 or delta > 0.15:
            delta = 0.033
        dt = delta / 0.01667

        self.w = float(max(self.width(), 1920))
        self.h = float(max(self.height(), 480))

        has_thunder = self.condition in ["thunderstorm", "thunderstorm-with-rain", "thunderstorm-with-hail"]
        if has_thunder:
            if now > self.next_lightning_time:
                self.lightnings.append(self._create_lightning_bolt())
                self.next_lightning_time = now + random.uniform(3.0, 8.0)

            self.flash_intensity = 0.0
            alive_lightnings = []
            for bolt in self.lightnings:
                self.flash_intensity = max(self.flash_intensity, bolt["opacity"] * 0.25)
                bolt["opacity"] -= bolt["decay"] * dt
                if bolt["opacity"] > 0:
                    alive_lightnings.append(bolt)
            self.lightnings = alive_lightnings
        else:
            self.flash_intensity = 0.0
            self.lightnings.clear()

        alive_particles = []
        for p in self.particles:
            if p["dying"]:
                p["opacity"] -= 0.007 * dt
                if p["opacity"] <= 0:
                    continue
            else:
                if p["opacity"] < p["target_opacity"]:
                    p["opacity"] = min(p["target_opacity"], p["opacity"] + 0.007 * dt)

            ptype = p["type"]
            if ptype == "rain":
                p["y"] += p["vy"] * dt
                p["x"] += p["vx"] * dt
                if p["y"] > self.h:
                    if p["dying"]:
                        p["opacity"] = 0
                        continue
                    self._create_splash(p["x"], self.h, QColor(174, 194, 224, int(p["opacity"] * 255)))
                    p["y"] = -p["length"]
                    p["x"] = random.uniform(-50, self.w + 50)

            elif ptype == "snow":
                p["y"] += p["vy"] * dt
                p["x"] += (p["vx"] + math.sin(p["y"] * p["swing_speed"] + p["swing_offset"]) * 0.5) * dt
                if p["y"] > self.h + p["radius"]:
                    if p["dying"]:
                        p["opacity"] = 0
                        continue
                    p["y"] = -p["radius"] * 2
                    p["x"] = random.uniform(0, self.w)

            elif ptype == "hail":
                p["y"] += p["speed_y"] * dt
                p["x"] += p["speed_x"] * dt
                if p["y"] > self.h:
                    if p["dying"]:
                        p["opacity"] = 0
                        continue
                    self._create_splash(p["x"], self.h, QColor(240, 245, 255, 200))
                    p["y"] = -p["radius"] * 2
                    p["x"] = random.uniform(0, self.w)

            elif ptype == "cloud":
                p["phase"] += p["phase_speed"] * dt
                p["x"] += p["speed"] * dt
                if p["x"] - p["radius"] > self.w:
                    if p["dying"]:
                        p["opacity"] = 0
                        continue
                    p["x"] = -p["radius"]
                    p["y"] = random.uniform(0, self.h * 0.7)


            alive_particles.append(p)

        self.particles = alive_particles

        alive_splashes = []
        for s in self.splashes:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vy"] += 0.15 * dt
            s["life"] -= s["decay"] * dt
            if s["life"] > 0:
                alive_splashes.append(s)
        self.splashes = alive_splashes

        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        clip_path = get_dashboard_rounded_path(float(self.width()), float(self.height()))
        painter.setClipPath(clip_path)

        if self.flash_intensity > 0.01:
            alpha = int(min(self.flash_intensity, 1.0) * 255 * 0.35)
            painter.fillRect(self.rect(), QColor(210, 220, 255, alpha))

        for bolt in self.lightnings:
            op = bolt["opacity"]
            if op <= 0:
                continue
            pen = QPen(QColor(220, 230, 255, int(op * 255)), bolt["width"])
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            for x1, y1, x2, y2, is_branch in bolt["segments"]:
                if is_branch:
                    branch_pen = QPen(QColor(200, 215, 255, int(op * 180)), max(bolt["width"] * 0.6, 1.0))
                    painter.setPen(branch_pen)
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                    painter.setPen(pen)
                else:
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        for p in self.particles:
            op = p["opacity"]
            if op <= 0.001:
                continue

            ptype = p["type"]
            if ptype == "rain":
                pen = QPen(QColor(174, 194, 224, int(op * 255)), p["width"])
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(QPointF(p["x"], p["y"]), QPointF(p["x"] + p["dx"], p["y"] + p["dy"]))

            elif ptype == "snow":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, int(op * 255)))
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["radius"], p["radius"])

            elif ptype == "hail":
                painter.setPen(QPen(QColor(255, 255, 255, int(op * 255)), 0.5))
                painter.setBrush(QColor(235, 240, 255, int(op * 215)))
                painter.drawEllipse(QPointF(p["x"], p["y"]), p["radius"], p["radius"])

            elif ptype == "cloud":
                current_op = min(op * (1.0 + math.sin(p["phase"]) * 0.1), 0.25)
                rad = p["radius"]
                painter.save()
                painter.setOpacity(current_op)
                painter.drawPixmap(
                    QRectF(p["x"] - rad, p["y"] - rad, rad * 2, rad * 2),
                    self.cloud_pixmap,
                    QRectF(0, 0, 256, 256),
                )
                painter.restore()


        painter.setPen(Qt.PenStyle.NoPen)
        for s in self.splashes:
            alpha = int(s["life"] * 255)
            col = QColor(s["color"])
            col.setAlpha(alpha)
            painter.setBrush(col)
            painter.drawEllipse(QPointF(s["x"], s["y"]), s["size"], s["size"])
