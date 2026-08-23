#!/usr/bin/env bash
PROJECT_DIR="/home/mucxep/Applications/rpi-dashboard"

cd "$PROJECT_DIR" || exit 1

export QT_QPA_PLATFORM=wayland

# Фоновый скрипт отключения/включения дисплея по расписанию
"$PROJECT_DIR/display_schedule.sh" &
SCHEDULER_PID=$!

trap 'kill -TERM $SCHEDULER_PID 2>/dev/null' EXIT

exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/main.py"
