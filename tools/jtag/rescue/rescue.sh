#!/bin/bash
# Halt the running (broken) firmware after the factory boot loader is done, load <image.bin> into RAM and start it
# with the boot loader's MMU state. Usage: ./rescue.sh <image.bin> [kHz]
# PATCH="addr=word addr=word" writes words into the loaded image before the start (see README).
cd "$(dirname "$0")"
IMAGE=$(realpath "${1:?usage: rescue.sh <image.bin> [kHz]}")
sudo pkill openocd; sleep 1
(sudo nohup openocd -s .. -f pi4.cfg -c "adapter speed ${2:-1000}; init" > oocd.log 2>&1 &); sleep 3
grep -q "Examination succeed" oocd.log || { echo "NO CPU"; tail -3 oocd.log; exit 1; }
python3 oc.py "capture halt" > h.txt
ttb=$(python3 oc.py "capture {arm mrc 15 0 2 0 0}" | grep -o "0x[0-9a-f]*"); echo TTB $ttb
[ "$ttb" = 0x8001c000 ] || { echo "boot loader not done, resume"; python3 oc.py "capture resume"; exit 2; }
cmds=("capture {arm mcr 15 0 1 0 0 0x50078}" "capture {load_image $IMAGE 0xc0000000 bin}")
for p in $PATCH; do cmds+=("capture {mww ${p%=*} ${p#*=}}" "capture {mdw ${p%=*} 1}"); done
cmds+=("capture {mdw 0xc0000000 2}" "capture {arm mcr 15 0 7 7 0 0}" "capture {arm mcr 15 0 8 7 0 0}"
  "capture {arm mcr 15 0 1 0 0 0x5107d}" "capture {reg cpsr 0x1d3}" "capture {reg pc 0xc0000000}" "capture resume")
python3 oc.py "${cmds[@]}" | grep -v "^$"
