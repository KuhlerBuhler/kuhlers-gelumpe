"""Native recording controller and its task-owned reader/writer."""
from pathlib import Path
from . import recording_service


PUBLIC_FIELDS = dict(CONTEXT=4, REQUEST=8, PHASE=12, ERROR=16, BYTES=20,
                     DROPPED=24, NUMBER=28, START=32, ELAPSED=36,
                     SELECTED=40, HELD=44, SETUP=48, CAPACITY=52, GAPS=56, DEFERRED=60,
                     UI_READY=64, VIEW_REQUEST=68,
                     # Behind NR_SETTING and the two PLAY bytes (72 to 74): reader faults (recording_reader.s RR_FAULT), the
                     # first since power-on and the last, eight words each: code, INFO[0], +4, +8, +12 (source pointer), +40,
                     # elapsed ticks of the take and OS ticks. ACK and STOP_ACK are the last start's and stop's wait for the
                     # DSP in ticks (all ones: it never showed).
                     FAULTS=76, FIRST=80, LAST=112, ACK=144, STOP_ACK=148)


def source(build='hacktribe', retarget=True):
    constants = '\n'.join(f'.equ NR_{key}, {value}' for key, value in PUBLIC_FIELDS.items())
    return recording_service.source(build, retarget) + '\n' + constants + '\n' + Path(__file__).with_suffix('.s').read_text()
