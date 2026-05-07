#!/bin/sh

export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority   # adjust username if needed

if [ -z "$1" ]; then
    echo "Usage: $0 <1|2>"
    exit 1
fi

OUTPUT="HDMI-$1"

# Check that output exists
if ! xrandr | grep -q "^$OUTPUT "; then
    echo "Output $OUTPUT not found."
    exit 1
fi

# Check if connected
if ! xrandr | grep -q "^$OUTPUT connected"; then
    echo "$OUTPUT is not connected."
    exit 1
fi

# Extract current mode (the one with *)
MODE=$(xrandr | awk -v output="$OUTPUT" '
    $0 ~ "^"output" connected" {found=1; next}
    found && /\*/ {print $1; exit}
')

if [ -z "$MODE" ]; then
    echo "Could not determine current mode for $OUTPUT."
    exit 1
fi

echo "Resetting $OUTPUT (current mode: $MODE)"

# Turn off
xrandr --output "$OUTPUT" --off
sleep 2

# Turn back on using same mode
xrandr --output "$OUTPUT" --mode "$MODE"

# Re-assert layout: HDMI-1 left of HDMI-2, HDMI-1 primary
xrandr --output HDMI-1 --primary --left-of HDMI-2

echo "Done."