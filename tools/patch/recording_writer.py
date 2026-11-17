"""Assemble the native recording file writer without firmware data."""
from pathlib import Path
from .arm import assemble
from . import synthaddr

FATFS = dict(OPEN=0xC009DB60, WRITE=0xC009DFB8, LSEEK=0xC009E404,
             CLOSE=0xC009E3DC, MKDIR=0xC009EB00)


def source(build='hacktribe'):
    if build not in ('hacktribe', 'stock', 'synth'):
        raise ValueError(f'unknown recording build: {build}')
    addresses = {name: synthaddr.tr(address) if build == 'synth' else address
                 for name, address in FATFS.items()}
    constants = '\n'.join(f'.equ REC_FS_{name}, {address:#x}' for name, address in addresses.items())
    return constants + '\n' + Path(__file__).with_suffix('.s').read_text()


def build(build='hacktribe', origin=0x100000):
    return assemble(source(build), origin=origin)
