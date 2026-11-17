"""Native recording controller and its task-owned reader/writer."""
from pathlib import Path
from . import recording_service


PUBLIC_FIELDS = dict(CONTEXT=4, REQUEST=8, PHASE=12, ERROR=16, BYTES=20,
                     DROPPED=24, NUMBER=28, START=32, ELAPSED=36,
                     SELECTED=40, HELD=44, SETUP=48, CAPACITY=52)


def source(build='hacktribe'):
    constants = '\n'.join(f'.equ NR_{key}, {value}' for key, value in PUBLIC_FIELDS.items())
    return recording_service.source(build) + '\n' + constants + '\n' + Path(__file__).with_suffix('.s').read_text()
