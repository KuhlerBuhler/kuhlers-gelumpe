#!/bin/bash
# Hold TRST low, wait for a power cycle, let ROM and boot loader finish (45 s), then run rescue.sh.
# Usage: ./late.sh <image.bin>   (PATCH is passed on)
cd "$(dirname "$0")"
IMAGE=$(realpath "${1:?usage: late.sh <image.bin>}")
sudo pkill openocd; sleep 0.3
sudo pinctrl set 5,6,11 ip pn; sudo pinctrl set 26 op dl
echo "waiting for power off"; while pinctrl lev 5 | grep -q 1; do sleep 0.05; done
echo "OFF, waiting for power on"; while ! pinctrl lev 5 | grep -q 1; do sleep 0.01; done
echo "ON $(date +%T)"; sleep 45
./rescue.sh "$IMAGE" 500
echo "rescue rc=$?"
