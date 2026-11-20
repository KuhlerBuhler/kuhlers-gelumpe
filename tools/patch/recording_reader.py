"""Assemble the task-context recording reader and capture command adapter."""
from pathlib import Path
from .arm import assemble
from . import recording_dsp, synthaddr


def source(build='hacktribe', retarget=True):
    if build not in ('hacktribe', 'stock', 'synth'):
        raise ValueError(f'unknown recording reader build: {build}')
    synth = build == 'synth'
    constants = dict(RR_FW_READ=0xC00141F8, RR_FW_WRITE_RAW=0xC00146B4,
                     RR_FW_GET=0xC0015C98, RR_FW_LOCK=0xC0000D80, RR_FW_UNLOCK=0xC0000CA8,
                     RR_TICKS=0xC06A292C, RR_CAPTURE=recording_dsp.CAPTURE,
                     RR_ENABLE=recording_dsp.ENABLE, RR_MAGIC_ADDRESS=recording_dsp.MAGIC_ADDRESS,
                     RR_MAGIC=recording_dsp.MAGIC, RR_TAP_STATE=recording_dsp.STATE,
                     RR_CHANNELS=1 if synth else 2, RR_HAS_SAMPLING=0 if synth else 1,
                     RR_INFO_HALFWORDS=8 if synth else 22,
                     RR_DSP_STATE=0xFF9031C8 if synth else 0xFF9031D0,
                     RR_SOURCE_POINTER=0xFF9031D4 if synth else 0xFF9031DC,
                     RR_DSP_RING=0x01371EC0 if synth else 0x01C722A0,
                     RR_INPUT=0xFF802810 if synth else 0xFF802878)
    if synth:
        constants['RR_FW_SEND'] = 0xC001251C
        if retarget:
            constants = {name: synthaddr.tr(value) if name.startswith('RR_FW_') or name == 'RR_TICKS' else value
                         for name, value in constants.items()}
    else:
        constants.update(RR_FW_BEGIN=0xC0014368, RR_FW_END=0xC00143E4)
    text = '\n'.join(f'.equ {name}, {value:#x}' for name, value in constants.items()) + '\n' + Path(__file__).with_suffix('.s').read_text()
    if synth:
        text += '\n' + Path(__file__).with_name('recording_capture_synth.s').read_text()
    return text


def build(build='hacktribe', origin=0x100000):
    return assemble(source(build), origin=origin)
