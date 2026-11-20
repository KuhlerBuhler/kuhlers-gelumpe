#!/bin/sh
# Usage: ./ocd.sh <adapter.cfg> <script.tcl>
#   ./ocd.sh e2-raspberrypi.cfg probe.tcl         (Raspberry Pi: run with sudo)
#   ./ocd.sh e2-xpack.cfg halt-at-entry.tcl       (CH347)
# OPENOCD=/path/to/openocd selects another binary.
cd "$(dirname "$0")" || exit 1
exec "${OPENOCD:-openocd}" -f "$1" -f "$2"
