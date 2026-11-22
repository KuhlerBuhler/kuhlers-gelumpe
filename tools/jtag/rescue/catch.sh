#!/bin/bash
# Hold TRST low until the CPU gets power (TMS pull-up goes high), then catch it in the boot loader and start
# <image.bin> at the firmware entry (catch.tcl). Usage: ./catch.sh <image.bin>. Did not catch it on 13.11.; late.sh did.
cd "$(dirname "$0")"
export IMAGE=$(realpath "${1:?usage: catch.sh <image.bin>}")
sudo pkill openocd; sleep 0.3
sudo pinctrl set 5,6,11 ip pn; sudo pinctrl set 26 op dl
echo "waiting for power off"; while pinctrl lev 5 | grep -q 1; do sleep 0.05; done
echo "OFF, waiting for power on"; while ! pinctrl lev 5 | grep -q 1; do sleep 0.01; done
echo "ON $(date +%T.%N)"
sudo -E openocd -s .. -f pi4.cfg -c "adapter speed 500" -f catch.tcl > catch.log 2>&1 &
