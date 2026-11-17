"""Assemble the command-task worker with its private reader and WAV writer."""
from pathlib import Path
from .arm import assemble
from . import recording_reader, recording_writer


def source(build='hacktribe'):
    return recording_writer.source(build) + '\n' + recording_reader.source(build) + '\n' + Path(__file__).with_suffix('.s').read_text()


def build(build='hacktribe', origin=0x100000):
    return assemble(source(build), origin=origin)
