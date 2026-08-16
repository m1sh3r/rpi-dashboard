from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

try:
    import psutil
except ImportError:
    psutil = None


class PcStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("Метрики ПК", self)
        layout.addWidget(self.title_label)

        self.cpu_label = QLabel("CPU: 0%", self)
        self.cpu_bar = QProgressBar(self)
        self.cpu_bar.setRange(0, 100)
        layout.addWidget(self.cpu_label)
        layout.addWidget(self.cpu_bar)

        self.ram_label = QLabel("RAM: 0%", self)
        self.ram_bar = QProgressBar(self)
        self.ram_bar.setRange(0, 100)
        layout.addWidget(self.ram_label)
        layout.addWidget(self.ram_bar)

        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)
        self.update_metrics()

    def update_metrics(self):
        if psutil is not None:
            cpu_percent = int(psutil.cpu_percent())
            ram_percent = int(psutil.virtual_memory().percent)

            self.cpu_label.setText(f"CPU: {cpu_percent}%")
            self.cpu_bar.setValue(cpu_percent)

            self.ram_label.setText(f"RAM: {ram_percent}%")
            self.ram_bar.setValue(ram_percent)
        else:
            self.cpu_label.setText("CPU: psutil не установлен")
            self.ram_label.setText("RAM: psutil не установлен")
