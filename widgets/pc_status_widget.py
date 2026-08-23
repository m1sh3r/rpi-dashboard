import math
from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .fonts import get_inter_font

SAMPLE_COUNT = 32


def format_number(value: float, digits: int = 1) -> str:
    s = f"{float(value):.{digits}f}"
    return s.replace(".", ",")


def format_percent(value: float) -> str:
    return f"{round(float(value or 0))}%"


def format_gb(bytes_val: float) -> str:
    gb = float(bytes_val or 0) / (1024.0**3)
    return f"{format_number(gb, 2)} ГБ"


def format_temperature(temp_val: float) -> str:
    if temp_val is None or temp_val <= 0 or not math.isfinite(float(temp_val)):
        return "н/д"
    return f"{format_number(temp_val, 1)} °C"


def format_network_mbit(bytes_per_sec: float) -> str:
    bits = max(float(bytes_per_sec or 0) * 8.0, 0.0)
    if bits >= 1000.0**3:
        return f"{format_number(bits / (1000.0**3), 2)} гбит/с"
    if bits >= 1000.0**2:
        return f"{format_number(bits / (1000.0**2), 2)} мбит/с"
    if bits >= 1000.0:
        return f"{format_number(bits / 1000.0, 2)} кбит/с"
    return f"{int(bits)} бит/с"


def format_duration(seconds: int) -> str:
    total = max(0, int(seconds or 0))
    days = total // (24 * 3600)
    hours = (total % (24 * 3600)) // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{days}:{hours:02d}:{minutes:02d}:{secs:02d}"


def clamp_percent(value: float) -> float:
    try:
        val = float(value)
        if not math.isfinite(val):
            return 0.0
        return max(0.0, min(100.0, val))
    except (ValueError, TypeError):
        return 0.0


class MetricCard(QWidget):
    def __init__(
        self,
        color_line: QColor,
        color_area: QColor,
        color_border: QColor,
        color_text_main: QColor,
        color_text_sub: QColor,
        caption: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.color_line = color_line
        self.color_area = color_area
        self.color_border = color_border
        self.color_text_main = color_text_main
        self.color_text_sub = color_text_sub
        self.caption = caption

        self.history = [0.0] * SAMPLE_COUNT
        self.main_value = "0%"
        self.sub_values: list[str] = []
        self.corner_radius = 26.0

    def add_sample(self, val: float):
        clamped = clamp_percent(val)
        self.history.pop(0)
        self.history.append(clamped)
        self.update()

    def set_history(self, history: list[float]):
        if len(history) >= SAMPLE_COUNT:
            self.history = [clamp_percent(v) for v in history[-SAMPLE_COUNT:]]
        else:
            padded = [0.0] * (SAMPLE_COUNT - len(history)) + [clamp_percent(v) for v in history]
            self.history = padded
        self.update()

    def set_content(self, main_val: str, sub_vals: list[str] = None):
        self.main_value = main_val
        self.sub_values = sub_vals or []
        self.update()

    def reset(self):
        self.history = [0.0] * SAMPLE_COUNT
        self.main_value = "0%"
        self.sub_values = []
        self.update()

    def _get_chart_y(self, value: float, height: float) -> float:
        pct = clamp_percent(value)
        if pct <= 0:
            return height + 10.0
        return height - (pct / 100.0) * height

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        r = self.corner_radius
        rect = QRectF(0, 0, w, h)

        card_path = QPainterPath()
        card_path.addRoundedRect(rect, r, r)

        painter.fillPath(card_path, QBrush(QColor(31, 31, 31, 225)))

        painter.setClipPath(card_path)

        n = len(self.history)
        if n >= 2:
            last_idx = max(n - 1, 1)
            points = []
            for i, val in enumerate(self.history):
                px = (i / float(last_idx)) * w
                py = self._get_chart_y(val, h)
                points.append(QPointF(px, py))

            area_path = QPainterPath()
            area_path.moveTo(-2.0, self._get_chart_y(self.history[0], h))
            area_path.lineTo(points[0].x(), points[0].y())
            for i in range(1, n):
                area_path.lineTo(points[i].x(), points[i].y())
            area_path.lineTo(w + 2.0, self._get_chart_y(self.history[-1], h))
            area_path.lineTo(w + 2.0, h + 2.0)
            area_path.lineTo(-2.0, h + 2.0)
            area_path.closeSubpath()

            painter.fillPath(area_path, QBrush(self.color_area))

            line_path = QPainterPath()
            line_path.moveTo(-2.0, self._get_chart_y(self.history[0], h))
            line_path.lineTo(points[0].x(), points[0].y())
            for i in range(1, n):
                line_path.lineTo(points[i].x(), points[i].y())
            line_path.lineTo(w + 2.0, self._get_chart_y(self.history[-1], h))

            line_pen = QPen(self.color_line, 1.2, Qt.SolidLine, Qt.FlatCap, Qt.RoundJoin)
            painter.strokePath(line_path, line_pen)

        painter.setClipping(False)

        inactive_pen = QPen(QColor(255, 255, 255, 14), 1.0)
        painter.setPen(inactive_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

        if max(self.history) > 1.5:
            active_pen = QPen(self.color_border, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(active_pen)
            painter.drawRoundedRect(rect.adjusted(0.6, 0.6, -0.6, -0.6), r, r)

        padding_x = 14.0
        padding_y = 12.0

        painter.setFont(get_inter_font(48, weight=700, is_pixel_size=True))
        painter.setPen(self.color_text_main)
        fm_main = QFontMetricsF(painter.font())
        main_w = fm_main.horizontalAdvance(self.main_value)
        main_ascent = fm_main.ascent()
        painter.drawText(QPointF(w - padding_x - main_w, padding_y + main_ascent), self.main_value)

        if self.sub_values:
            painter.setFont(get_inter_font(20, weight=400, is_pixel_size=True))
            painter.setPen(self.color_text_sub)
            fm_sub = QFontMetricsF(painter.font())
            cur_y = padding_y + main_ascent + fm_sub.height() + 2.0
            for sub_text in self.sub_values:
                sub_w = fm_sub.horizontalAdvance(sub_text)
                painter.drawText(QPointF(w - padding_x - sub_w, cur_y), sub_text)
                cur_y += fm_sub.lineSpacing() + 2.0

        if self.caption:
            painter.setFont(get_inter_font(16, weight=400, is_pixel_size=True))
            painter.setPen(self.color_text_sub)
            fm_cap = QFontMetricsF(painter.font())
            cap_w = fm_cap.horizontalAdvance(self.caption)
            max_cap_w = w - padding_x * 2.0
            if cap_w > max_cap_w:
                elided = fm_cap.elidedText(self.caption, Qt.ElideRight, max_cap_w)
                elided_w = fm_cap.horizontalAdvance(elided)
                painter.drawText(QPointF((w - elided_w) / 2.0, h - padding_y), elided)
            else:
                painter.drawText(QPointF((w - cap_w) / 2.0, h - padding_y), self.caption)


class PcStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.disks_history: dict[str, list[float]] = {}
        self.disk_cards: list[MetricCard] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        top_line = QWidget(self)
        top_layout = QHBoxLayout(top_line)
        top_layout.setContentsMargins(12, 0, 12, 0)
        top_layout.setSpacing(28)

        self.net_tx_arrow = QLabel("↑", top_line)
        self.net_tx_arrow.setFont(get_inter_font(28, weight=400, is_pixel_size=True))
        self.net_tx_arrow.setStyleSheet("color: rgba(225, 220, 212, 0.85);")

        self.net_tx_val = QLabel("0 бит/с", top_line)
        self.net_tx_val.setFont(get_inter_font(28, weight=700, is_pixel_size=True))
        self.net_tx_val.setStyleSheet("color: rgba(225, 220, 212, 0.95);")

        self.net_rx_arrow = QLabel("↓", top_line)
        self.net_rx_arrow.setFont(get_inter_font(28, weight=400, is_pixel_size=True))
        self.net_rx_arrow.setStyleSheet("color: rgba(225, 220, 212, 0.85);")

        self.net_rx_val = QLabel("0 бит/с", top_line)
        self.net_rx_val.setFont(get_inter_font(28, weight=700, is_pixel_size=True))
        self.net_rx_val.setStyleSheet("color: rgba(225, 220, 212, 0.95);")

        net_box = QHBoxLayout()
        net_box.setSpacing(28)
        
        tx_box = QHBoxLayout()
        tx_box.setSpacing(8)
        tx_box.addWidget(self.net_tx_arrow)
        tx_box.addWidget(self.net_tx_val)

        rx_box = QHBoxLayout()
        rx_box.setSpacing(8)
        rx_box.addWidget(self.net_rx_arrow)
        rx_box.addWidget(self.net_rx_val)

        net_box.addStretch(1)
        net_box.addLayout(tx_box)
        net_box.addLayout(rx_box)
        net_box.addStretch(1)

        self.uptime_caption = QLabel("Время работы", top_line)
        self.uptime_caption.setFont(get_inter_font(20, weight=400, is_pixel_size=True))
        self.uptime_caption.setStyleSheet("color: rgba(225, 220, 212, 0.72);")

        self.uptime_val_label = QLabel("0:00:00:00", top_line)
        self.uptime_val_label.setFont(get_inter_font(28, weight=700, is_pixel_size=True))
        self.uptime_val_label.setStyleSheet("color: rgba(225, 220, 212, 0.95);")

        uptime_box = QHBoxLayout()
        uptime_box.setSpacing(12)
        uptime_box.addStretch(1)
        uptime_box.addWidget(self.uptime_caption)
        uptime_box.addWidget(self.uptime_val_label)
        uptime_box.addStretch(1)

        top_layout.addLayout(net_box, 18)
        top_layout.addLayout(uptime_box, 12)
        main_layout.addWidget(top_line, 1)

        middle_cards = QWidget(self)
        middle_layout = QHBoxLayout(middle_cards)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(10)

        self.cpu_card = MetricCard(
            color_line=QColor(43, 178, 237, 160),
            color_area=QColor(43, 178, 237, 24),
            color_border=QColor(43, 178, 237, 55),
            color_text_main=QColor(214, 219, 222),
            color_text_sub=QColor(167, 175, 180),
            caption="Активность ЦП",
            parent=middle_cards,
        )
        self.memory_card = MetricCard(
            color_line=QColor(168, 82, 224, 160),
            color_area=QColor(168, 82, 224, 24),
            color_border=QColor(168, 82, 224, 55),
            color_text_main=QColor(218, 215, 221),
            color_text_sub=QColor(174, 170, 178),
            caption="Использование памяти",
            parent=middle_cards,
        )
        self.gpu_card = MetricCard(
            color_line=QColor(232, 48, 125, 160),
            color_area=QColor(232, 48, 125, 24),
            color_border=QColor(232, 48, 125, 55),
            color_text_main=QColor(221, 214, 217),
            color_text_sub=QColor(178, 169, 173),
            caption="Активность ГП",
            parent=middle_cards,
        )

        middle_layout.addWidget(self.cpu_card, 10)
        middle_layout.addWidget(self.memory_card, 10)
        middle_layout.addWidget(self.gpu_card, 10)
        main_layout.addWidget(middle_cards, 4)

        self.disks_container = QWidget(self)
        self.disks_layout = QHBoxLayout(self.disks_container)
        self.disks_layout.setContentsMargins(0, 0, 0, 0)
        self.disks_layout.setSpacing(10)

        main_layout.addWidget(self.disks_container, 3)

    def _parse_disks(self, raw_disks) -> list[dict]:
        if not raw_disks or not isinstance(raw_disks, list):
            return []

        parsed = []
        for idx, disk in enumerate(raw_disks):
            if not isinstance(disk, dict):
                continue

            raw_label = disk.get("label") or disk.get("Label") or disk.get("mountpoint") or disk.get("device") or f"Диск {idx + 1}"
            label = str(raw_label).rstrip("\\/").strip() or f"Диск {idx + 1}"

            name = str(disk.get("name") or disk.get("Name") or disk.get("volumeName") or disk.get("VolumeLabel") or "").strip()
            total_b = float(disk.get("totalBytes") or disk.get("TotalBytes") or disk.get("total") or 0)
            free_b = float(disk.get("freeBytes") or disk.get("FreeBytes") or disk.get("free") or 0)
            used_b = float(disk.get("usedBytes") or disk.get("UsedBytes") or disk.get("used") or 0)

            if free_b == 0 and total_b > 0 and used_b > 0:
                free_b = max(0.0, total_b - used_b)

            if "usagePercent" in disk and disk["usagePercent"] is not None:
                usage_pct = float(disk["usagePercent"])
            elif "UsagePercent" in disk and disk["UsagePercent"] is not None:
                usage_pct = float(disk["UsagePercent"])
            elif "percent" in disk and disk["percent"] is not None:
                usage_pct = float(disk["percent"])
            elif total_b > 0:
                usage_pct = ((total_b - free_b) / total_b) * 100.0
            else:
                usage_pct = 0.0

            parsed.append({
                "label": label,
                "name": name,
                "totalBytes": total_b,
                "freeBytes": free_b,
                "usagePercent": clamp_percent(usage_pct),
            })

        return parsed

    def update_data(self, payload: dict):
        if not payload or not payload.get("data"):
            return
        data = payload["data"]

        uptime_sec = data.get("uptimeSeconds") or data.get("UptimeSeconds") or 0
        self.uptime_val_label.setText(format_duration(uptime_sec))

        net = data.get("network") or data.get("Network") or {}
        tx = net.get("txBytesPerSecond") or net.get("TxBytesPerSecond") or 0
        rx = net.get("rxBytesPerSecond") or net.get("RxBytesPerSecond") or 0
        self.net_tx_val.setText(format_network_mbit(tx))
        self.net_rx_val.setText(format_network_mbit(rx))

        cpu = data.get("cpu") or data.get("Cpu") or {}
        cpu_usage = clamp_percent(cpu.get("usagePercent") if "usagePercent" in cpu else cpu.get("UsagePercent", 0))
        self.cpu_card.add_sample(cpu_usage)
        self.cpu_card.set_content(format_percent(cpu_usage))

        mem = data.get("memory") or data.get("Memory") or {}
        total_ram = float(mem.get("totalBytes") or mem.get("TotalBytes") or 1)
        used_ram = float(mem.get("usedBytes") or mem.get("UsedBytes") or 0)
        ram_pct = (used_ram / total_ram) * 100.0 if total_ram > 0 else 0.0

        commit_used = float(mem.get("commitUsedBytes") or mem.get("CommitUsedBytes") or 0)
        swap = data.get("swap") or data.get("Swap") or {}
        swap_used = float(swap.get("usedBytes") or swap.get("UsedBytes") or max(commit_used - used_ram, 0.0))

        self.memory_card.add_sample(ram_pct)
        self.memory_card.set_content(
            main_val=format_gb(used_ram),
            sub_vals=[f"Подкачка {format_gb(swap_used)}"],
        )

        gpu = data.get("gpu") or data.get("Gpu") or {}
        gpu_usage = clamp_percent(gpu.get("usagePercent") if "usagePercent" in gpu else gpu.get("UsagePercent", 0))
        gpu_vram = float(gpu.get("memoryUsedBytes") or gpu.get("MemoryUsedBytes") or 0)
        gpu_temp = gpu.get("temperatureC") if "temperatureC" in gpu else gpu.get("TemperatureC")

        self.gpu_card.add_sample(gpu_usage)
        self.gpu_card.set_content(
            main_val=format_percent(gpu_usage),
            sub_vals=[
                f"VRAM {format_gb(gpu_vram)}",
                format_temperature(gpu_temp),
            ],
        )

        raw_disks = data.get("disks") or data.get("Disks") or []
        parsed_disks = self._parse_disks(raw_disks)

        next_disks_history = {}
        for disk in parsed_disks:
            key = disk["label"]
            h = self.disks_history.get(key) or ([0.0] * SAMPLE_COUNT)
            h = h[1:] + [disk["usagePercent"]]
            next_disks_history[key] = h
        self.disks_history = next_disks_history

        while len(self.disk_cards) < len(parsed_disks):
            card = MetricCard(
                color_line=QColor(38, 217, 98, 160),
                color_area=QColor(38, 217, 98, 24),
                color_border=QColor(38, 217, 98, 55),
                color_text_main=QColor(200, 208, 203),
                color_text_sub=QColor(159, 172, 163),
                caption="",
                parent=self.disks_container,
            )
            card.corner_radius = 26.0
            self.disks_layout.addWidget(card, 1)
            self.disk_cards.append(card)

        for i, card in enumerate(self.disk_cards):
            if i < len(parsed_disks):
                disk = parsed_disks[i]
                key = disk["label"]
                pct = disk["usagePercent"]
                free_b = disk["freeBytes"]
                name = disk["name"]
                caption = f"{key} ({name})" if name else key

                card.caption = caption
                card.set_history(self.disks_history.get(key, []))
                card.set_content(
                    main_val=format_percent(pct),
                    sub_vals=[f"Свободно {format_gb(free_b)}"],
                )
                card.show()
            else:
                card.hide()

    def reset(self):
        self.net_tx_val.setText("0 бит/с")
        self.net_rx_val.setText("0 бит/с")
        self.uptime_val_label.setText("0:00:00:00")
        self.cpu_card.reset()
        self.memory_card.reset()
        self.gpu_card.reset()
        self.disks_history.clear()
        for card in self.disk_cards:
            card.reset()
            card.hide()
