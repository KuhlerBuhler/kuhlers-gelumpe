# Linux ALSA SysEx transport

`alsa-sysex.c` sends one complete SysEx frame from stdin to an explicitly
selected ALSA sequencer port. The encoder produces events of at most
256 bytes. Each event is drained and followed by a 2 ms pause. The frame
keeps one opening F0 and one closing F7; the transport adds neither headers
nor message boundaries between events.

Build on Linux with a C compiler and the ALSA development headers
(`libasound2-dev` on Debian/Ubuntu):

```sh
cc -std=c11 -Wall -Wextra -Werror tools/alsa-sysex.c -lasound -o /tmp/alsa-sysex
```

The destination must come from the selected port, not a saved client number:
ALSA client numbers can change after reconnecting a device. The helper checks
that the destination exists and accepts output, then connects its source
port before sending. It rejects incomplete frames, embedded status bytes,
multiple frames and input larger than 1 MiB before opening an output port.
Every encoder, event-output and drain error stops transmission without retry.
A zero exit status means the ALSA writes succeeded, not that the device
acknowledged the command. Command validation, SimDevice preflight, backups,
reply matching and readback belong to the caller.

For measurement scripts using mido, `alsa_mido.PacedOutput(port_name, binary)`
implements `send(message)` and `close()` for SysEx. It uses the numeric
address at the end of the selected ALSA port name and a bounded subprocess.
The MIDI input remains with mido; the sender does not receive replies.

Run integration checks on Linux with `python-rtmidi` and `mido`:

```sh
python3 tools/test_alsa_sysex.py /tmp/alsa-sysex
```

The tests open uniquely named virtual ports only. They check exact delivery
of frames up to 59,894 bytes, the mido adapter and refusal of invalid input.
They do not select an Electribe or another hardware destination. Synthetic
payloads contain no Korg data.

The 256-byte/2-ms configuration was measured between virtual ALSA ports
and on the sampler with unchanged RAM data up to 52,400 bytes.
Device results and limits are recorded in
[the protocol measurements](../docs/messungen/2026-10-08-geraeteprotokoll.md).
This tool is separate from the editor's browser Web MIDI transport.
