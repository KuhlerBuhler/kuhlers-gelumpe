"""Assemble the task-context recording reader for the sampler builds."""
from pathlib import Path
from .arm import assemble
from . import recording_dsp


def source(build='hacktribe'):
    if build not in ('hacktribe', 'stock'):
        raise ValueError('the stereo capture reader supports the sampler builds')
    constants = dict(RR_FW_READ=0xC00141F8, RR_FW_WRITE_RAW=0xC00146B4,
                     RR_FW_GET=0xC0015C98, RR_FW_LOCK=0xC0000D80, RR_FW_UNLOCK=0xC0000CA8,
                     RR_FW_BEGIN=0xC0014368, RR_FW_END=0xC00143E4,
                     RR_TICKS=0xC06A292C, RR_CAPTURE=recording_dsp.CAPTURE,
                     RR_ENABLE=recording_dsp.ENABLE, RR_MAGIC_ADDRESS=recording_dsp.MAGIC_ADDRESS,
                     RR_MAGIC=recording_dsp.MAGIC, RR_TAP_STATE=recording_dsp.STATE)
    return '\n'.join(f'.equ {name}, {value:#x}' for name, value in constants.items()) + '\n' + Path(__file__).with_suffix('.s').read_text()


def build(build='hacktribe', origin=0x100000):
    return assemble(source(build), origin=origin)
