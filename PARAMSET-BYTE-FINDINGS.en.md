# Byte Targets for Plugin Controls

As of 2026-11-06. [Deutsche Fassung](PARAMSET-BYTE-FINDINGS.md).

This note collects the known Pattern bytes for the thirteen writable `korg.parts[i]` fields, six buttons, the CUTOFF, Sample/OSC, Modulation and IFX Type encoders, and the SHIFT + OSC PITCH alternate function for Glide.

All offsets are relative to the pointer to the active Pattern. The writable-field table gives Part 0, the first Part. For these thirteen fields, the Part byte for Part n is `field offset + 0x330 * n`; its copy is `copy offset + 0x24 * n`. The native writer test confirms these strides. The buttons and the Sample/OSC, Modulation and IFX Type encoders were checked only on Part 0. CUTOFF and Glide were checked for every Part in the emulator.

## Writable Part Properties

The writer sets the main byte and its listed copy to the same value. Each field has its own copy offset because the distance from the main byte is not the same for every field.

| No. | Assignment | Part 0 main byte | Part 0 copy |
|---:|---|---:|---:|
| 1 | `korg.parts[0].level = value` | `0x81C` | `0x404A` |
| 2 | `korg.parts[0].pan = value` | `0x81D` | `0x404B` |
| 3 | `korg.parts[0].pitch = value` | `0x828` | `0x4052` |
| 4 | `korg.parts[0].resonance = value` | `0x812` | `0x4040` |
| 5 | `korg.parts[0].egInt = value` | `0x813` | `0x4041` |
| 6 | `korg.parts[0].modDepth = value` | `0x816` | `0x4044` |
| 7 | `korg.parts[0].modSpeed = value` | `0x815` | `0x4043` |
| 8 | `korg.parts[0].attack = value` | `0x818` | `0x4046` |
| 9 | `korg.parts[0].decay = value` | `0x819` | `0x4047` |
| 10 | `korg.parts[0].ifxEdit = value` | `0x826` | `0x4050` |
| 11 | `korg.parts[0].oscEdit = value` | `0x80F` | `0x403D` |
| 12 | `korg.parts[0].cutoff = value` | `0x811` | `0x403F` |
| 13 | `korg.parts[0].glide = value` | `0x829` | `0x4053` |

These offsets come from emulator comparisons of knob movements. The copy offsets are also recorded in the internal writer and its native test. See [knob movements](docs/messungen/2026-10-15-tap-motion.md), [writer](tools/patch/script_hw.s) and [writer test](tools/patch/test_script_hw.py).

### CUTOFF and Glide Mirrors for Every Part

The mirror locations and strides were checked for all 16 Parts using panel input in the emulator. The runtime writer synchronizes the main byte and mirror for both fields. The measurement establishes RAM changes, not an audible effect on the device.

| Field | Part 0 main byte | Part 0 mirror | Part n main byte | Part n mirror |
|---|---:|---:|---|---|
| `cutoff` | `0x811` | `0x403F` | `0x811 + 0x330 * n` | `0x403F + 0x24 * n` |
| `glide` | `0x829` | `0x4053` | `0x829 + 0x330 * n` | `0x4053 + 0x24 * n` |

CUTOFF was tested by moving the CUTOFF encoder (encoder index `2`) down one step. The main byte and mirror on every Part changed together from 127 to 126. For Glide, SHIFT (`0x0A`) was held while moving the OSC PITCH knob (knob index `2`). The input value was `200 + 2 * Part`; the firmware set Glide to `100 + Part`. In both tests, exactly the main byte and mirror changed to the same value on each Part. See the [CUTOFF and Glide mirror measurement](docs/messungen/2026-11-06-glide-mirror.md).

After writing any of the thirteen values, the Sampler runtime calls the firmware parameter-apply path: `0xC0048460` with the target Part and field-specific code, then `0xC0059720` with the Part, setter ID and value. Signed PAN, EG INT and OSC PITCH values are shifted by 64 for the setter. The mapping is derived from Hacktribe firmware 2.02 and was checked against Pattern bytes in the emulator; the emulator does not model the DSP. The audible effect still needs to be checked on the device. The corresponding Synth firmware path has not yet been mapped. See [parameter refresh](docs/messungen/2026-11-06-part-param-refresh.md).

The type-12 notification is no longer sent when writing. It may still be useful when the UI needs to refresh a parameter display; it is not a confirmed DSP refresh. See the [reminder](PARAMETER-REFRESH-REMINDER.md).

## Buttons and Encoders

The following results are Pattern RAM comparisons in the emulator using a personal Hacktribe `SYSTEM.VSB`, no flash image and the startup Pattern. Each probe used a fresh emulator state. Buttons were pressed once; both directions were tested for encoders. The table lists every stable changed byte in the Pattern block.

| No. | Control | Part 0 main bytes | Other Part 0 bytes | Observation |
|---:|---|---|---|---|
| 12 | LPF button `0x12` | Filter type `0x810`: `1 -> 2` | `0x403E`: `1 -> 2` | Main byte and copy match |
| 13 | HPF button `0x14` | Filter type `0x810`: `1 -> 7` | `0x403E`: `1 -> 7` | Main byte and copy match |
| 14 | BPF button `0x16` | Filter type `0x810`: `1 -> 12` | `0x403E`: `1 -> 12` | Main byte and copy match |
| 15 | MFX Send button `0x1A` | MFX Send `0x81F`: `1 -> 0` | `0x404D`: `1 -> 0` | Main byte and copy match |
| 16 | Amp EG button `0x20` | EG on `0x81E`: `0 -> 1` | `0x404C`: `0 -> 1` | Main byte and copy match |
| 17 | IFX On button `0x21` | IFX on `0x824`: `0 -> 1` | `0x404E`: `0 -> 127` | The copy uses a different encoding |
| 18 | Sample/OSC encoder `1`, direction `+1` | Sample low byte `0x80C`: `0 -> 1` | `0x403A`: `0 -> 1` | Only the low byte changes |
|  | Sample/OSC encoder `1`, direction `-1` | Sample `0x80C-0x80D`: `0, 0 -> 17, 1`; OSC Edit `0x80F`: `0 -> 32` | Sample `0x403A-0x403B`: `0, 0 -> 17, 1`; OSC Edit `0x403D`: `0 -> 32` | Sample becomes little-endian `0x0111` |
| 19 | Modulation encoder `3`, direction `+1` | Mod type `0x814`: `0 -> 1`; Speed `0x815`: `23 -> 32`; Depth `0x816`: `0 -> 97` | `0x4042`: `0 -> 1`; `0x4043`: `23 -> 32`; `0x4044`: `0 -> 97` | All three bytes and their copies change |
|  | Modulation encoder `3`, direction `-1` | Mod type `0x814`: `0 -> 71`; Speed `0x815`: `23 -> 42`; Depth `0x816`: `0 -> 127` | `0x4042`: `0 -> 71`; `0x4043`: `23 -> 42`; `0x4044`: `0 -> 127` | All three bytes and their copies change |
| 20 | IFX Type encoder `4`, direction `+1` | IFX type `0x825`: `0 -> 1` | `0x404F`: `0 -> 1` | Main byte and copy match |
|  | IFX Type encoder `4`, direction `-1` | IFX type `0x825`: `0 -> 48` | `0x404F`: `0 -> 48` | Main byte and copy match |

Encoder values depend on the starting Pattern state. Sample/OSC and Modulation in particular change multiple fields during a movement. The IFX copies are at `0x404E` and `0x404F`, not at the same relative position as most other copies.

## Not Confirmed

- The six buttons and three encoders were measured in the emulator, not on the device.
- Copies for other Parts have not been checked for the six buttons, Sample/OSC, Modulation or IFX Type.
- CUTOFF and SHIFT + OSC PITCH were checked for every Part in the emulator, not on the device.
- A changed byte alone does not prove that the second location causes an audible change on the device.
- Sample/OSC and Modulation were checked with the startup Pattern. Other presets may have different starting values and therefore different resulting bytes.
