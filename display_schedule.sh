#!/usr/bin/env bash

OUTPUT="HDMI-A-1"
STAMP_DIR="/tmp/display_schedule"
mkdir -p "$STAMP_DIR"

OFF_STAMP="$STAMP_DIR/off_stamp"
ON_STAMP="$STAMP_DIR/on_stamp"

while true; do
    NOW="$(date +%H:%M)"
    TODAY="$(date +%F)"

    if [ "$NOW" = "00:10" ]; then
        if [ ! -f "$OFF_STAMP" ] || [ "$(cat "$OFF_STAMP" 2>/dev/null)" != "$TODAY" ]; then
            wlr-randr --output "$OUTPUT" --off && echo "$TODAY" > "$OFF_STAMP"
        fi
    fi

    if [ "$NOW" = "06:30" ]; then
        if [ ! -f "$ON_STAMP" ] || [ "$(cat "$ON_STAMP" 2>/dev/null)" != "$TODAY" ]; then
            wlr-randr --output "$OUTPUT" --on && echo "$TODAY" > "$ON_STAMP"
        fi
    fi

    sleep 10
done
