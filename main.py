import sys
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from api import WeatherClient
from widgets import (
    AnalogClock,
    CalendarWidget,
    PcStatusWidget,
    WeatherWidget,
)


class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.is_pc_online = False

        self.setWindowTitle("RPI Dashboard")
        self.setFixedSize(1920, 480)
        self.setStyleSheet("background-color: #000000; color: #ffffff;")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        left_container = QFrame(self)
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)

        self.clock = AnalogClock(left_container)
        self.calendar = CalendarWidget(left_container)

        left_layout.addWidget(self.clock, 1)
        left_layout.addWidget(self.calendar, 1)

        main_layout.addWidget(left_container, 1)

        right_container = QFrame(self)
        self.right_layout = QVBoxLayout(right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(10)

        self.weather = WeatherWidget(right_container)
        self.pc_status = PcStatusWidget(right_container)

        self.right_layout.addWidget(self.weather, 1)
        self.right_layout.addWidget(self.pc_status, 1)

        main_layout.addWidget(right_container, 1)

        self.set_online_state(self.is_pc_online)

        self.weather_client = WeatherClient(self)
        self.weather_client.weather_updated.connect(self.weather.update_data)
        self.weather_client.weather_error.connect(self.weather.set_error)
        self.weather_client.update_weather()

    def set_online_state(self, is_online: bool):
        self.is_pc_online = is_online
        if is_online:
            self.weather.set_compact_mode(True)
            self.pc_status.show()
        else:
            self.weather.set_compact_mode(False)
            self.pc_status.hide()


def main():
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
