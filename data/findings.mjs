/**
 * What is known about the units, as opposed to where things sit in memory.
 *
 * Which unit runs in the second insert stage, where a parameter is off,
 * which level is unplayable: knowledge about behaviour, measured on hardware
 * or checked against the factory presets. Same rules for source and evidence
 * as the device map; test/map.test.mjs holds both to them.
 *
 * A finding says what was observed, not what is forbidden. Anything missing
 * here is untested, which is neither forbidden nor safe.
 */
const SWEEP = "measure:2026-09-21/stage2-sweep";
const CHAINS = "measure:2026-09-14/stage2-chains";
const RING = "measure:2026-09-21/ring-mod-chain";
const LEVEL_MOD = "measure:2026-09-21/level-mod";
const LOUD = "measure:2026-09-21/loudness";
const MOD_STAGE2 = "measure:2026-10-15/modulation-stufe2";

const stage2 = (unit, verdict, note, evidence) => ({
  id: `stage2.${unit.toString(16).padStart(2, "0")}`, kind: "stage2", unit, verdict, note, source: "measured", evidence,
});

export default [
  stage2(0x01, "silent", "mkp2_comp: runs, passes no audio", SWEEP),
  stage2(0x02, "fatal", "sr1_comp: crash", SWEEP),
  stage2(0x03, "ok", "cheap_comp", SWEEP),
  stage2(0x04, "ok", "punch", SWEEP),
  stage2(0x05, "ok", "limiter", SWEEP),
  stage2(0x06, "ok", "eq_2_band, and Korg uses it itself", SWEEP),
  stage2(0x07, "ok", "eq_4_band", SWEEP),
  stage2(0x08, "silent", "exciter: runs, passes no audio", SWEEP),
  stage2(0x09, "fatal", "decimator: crash", SWEEP),
  stage2(0x0a, "ok", "filter, and Korg uses it itself", CHAINS),
  stage2(0x10, "ok", "acid driver, and Korg uses it itself", CHAINS),
  stage2(0x16, "silent", "ring mod: runs, passes no audio (heard 2026-09-21)", RING),
  stage2(0x18, "fatal", "short delay: kills sound device-wide, needs a restart", CHAINS),

  { id: "stage1Solo.09", kind: "stage1NeedsSolo", unit: 0x09, note: "decimator crashed with 0x0a behind it; alone it runs", source: "measured", evidence: CHAINS },
  { id: "stage1Solo.16", kind: "stage1NeedsSolo", unit: 0x16, note: "ring mod with any second stage behind it plays nothing", verdict: "silent", source: "measured", evidence: RING },

  { id: "factoryChains", kind: "factoryChains", chains: [[0x10, 0x06], [0x0a, 0x0a], [0x0a, 0x10]], source: "measured", evidence: "factory-check:stage2-factory-chains" },
  { id: "mfxMute", kind: "mfxMute", unit: 0x27, note: "the mute unit an insert record carries in its unused master field", source: "measured", evidence: "factory-check:insert-master-field" },
  { id: "mfxDeviceRange", kind: "mfxDeviceRange", range: [0x27, 0x40], note: "master units; one inside an insert chain hangs the device", source: "derived", evidence: "derived:hacktribe-editor/src/hacktribe_editor/utils/ht_fx_ram_format.py" },

  { id: "offAt.dry_wet", kind: "offAt", param: "dry_wet", value: 0, source: "korg-spec", evidence: "korg-spec:M3 Parameter Guide, Wet/Dry" },
  { id: "offAt.dry_level", kind: "offAt", param: "dry_level", value: 0, source: "korg-spec", evidence: "korg-spec:M3 Parameter Guide, Dry Level" },
  { id: "offAt.level_mod_int", kind: "offAt", param: "level_mod_int", value: 63, note: "bipolar; 63 is the quiet point, not a bypass", source: "measured", evidence: LEVEL_MOD },
  { id: "offAt.mod_int", kind: "offAt", param: "mod_int", value: null, note: "nobody has worked out where off is", source: "unknown" },
  { id: "offAt.loopswitch", kind: "offAt", param: "loopswitch", value: 0, source: "derived", evidence: "derived:modding notes v3, 08-presets-bauen" },
  { id: "offAt.pad_on", kind: "offAt", param: "pad_on", value: 0, source: "derived", evidence: "derived:modding notes v3, 08-presets-bauen" },

  { id: "loudness", kind: "loudness", outputCeiling: 90, outputTypical: [30, 60], feedbackCeiling: 90,
    note: "output_level at 124 is unplayable; delay feedback above 90 stacks until nothing is left", source: "measured", evidence: LOUD },

  { id: "usableLevel", kind: "usableLevel", range: [38, 60], note: "output levels of 38 to 60 were playable by ear", source: "measured", evidence: LOUD },
  { id: "unplayable.distortionOutput", kind: "unplayableLevel", unit: 0x0f, param: "output_level", value: 124, note: "output_level 124 in a distortion preset was unplayably loud", source: "measured", evidence: LOUD },
  { id: "unplayable.levelModGain", kind: "unplayableLevel", unit: 0x15, param: "output_gain", value: 95, note: "output_gain 95 on the level modulator overdrove at every knob position; Korg's own Pumper, Repeater and Slicer sit at 32 to 36", source: "measured", evidence: LOUD },

  { id: "playRow.15", kind: "playRowResyncs", units: [0x15], note: "a play row on lfo_reset gives a deterministic start; without it the modulator free-runs", source: "measured", evidence: LEVEL_MOD },

  { id: "glideDroppedByPatternSysex", kind: "transportGap", field: "part.glide", transport: "pattern-sysex",
    note: "a pattern sent over SysEx 0x40 comes back with glide at 0; CC 81 sets it", source: "measured", evidence: "measure:2026-09-22/pattern-write-glide" },

  { id: "sampleName.field", kind: "sampleName", width: 16,
    note: "the name field is 16 bytes, written NUL padded; a shorter name (Blech) was read back and shown on the display", source: "measured", evidence: "measure:2026-10-07/sample-name-ram" },
  { id: "sampleTune.seen", kind: "sampleTune", seen: [-16, -12, 0],
    note: "tune values seen on the device: 0, -16 (the samples with index 654 and 711) and -12 (written, the pitch changed audibly); the scale was not measured", source: "measured", evidence: "measure:2026-10-07/sample-metadaten-ram" },
  { id: "sampleUnused.emulator", kind: "sampleUnused",
    note: "emulator without a sample card: unused slots hold the name SampleNNN, 48000 Hz and PCM length 0, so only the PCM length marks them; not measured on a device", source: "measured", evidence: "measure:2026-10-07/sample-metadaten-ram" },
  { id: "sampleEdit.ramOnly", kind: "sampleRamOnly",
    note: "a name written to RAM left the SD file and its backup unchanged; whether it survives a restart or EXPORT ALL SAMPLE was not measured", source: "measured", evidence: "measure:2026-10-07/sample-name-ram" },

  { id: "refuted.lfoResetHeldSilences", kind: "refuted", note: "held lfo_reset does not silence the level modulator (heard 2026-09-21)", source: "measured", evidence: LEVEL_MOD },
  { id: "refuted.lfoResetHeldSyncs", kind: "refuted", note: "holding it without a play row does not keep the beat, it loses it entirely", source: "measured", evidence: LEVEL_MOD },
  { id: "refuted.levelModSourceFour", kind: "refuted", note: "level_mod_source = 4 is what the factory Pumper uses and it works", source: "measured", evidence: LEVEL_MOD },
  { id: "effectsAlwaysRun", kind: "dspLoad", note: "insert and master effects are processed all the time, also while not used or not heard; a part's IFX type costs DSP load even with IFX off, and changing a type rebuilds the effect slot", source: "korg-spec", evidence: "korg-spec:Korg FAQ 368, notes missing during playback" },
  { id: "heavyIfx", kind: "dspLoad", ifx: [6, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30], note: "high-load insert types (Ring Modulator, the delays, Roller 1/32, One Delay, Short Delay, Ring Delay 1/2, Chorus, the flangers); Korg recommends IFX 01 Punch on parts that do not use an insert and filter type Off on parts without filter, Voice Assign Mono, Alternate 13-14 and 15-16 On, Part Priority High against dropped notes", source: "korg-spec", evidence: "korg-spec:Korg FAQ 368, notes missing during playback" },

  // The modulation table, measured in the emulator (not on a device). Offsets are those of the map window of table.modType.
  { id: "modType.unreadBytes", kind: "modTable", offsets: [0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1f, 0x22, 0x23, 0x25, 0x26, 0x27, 0x2a, 0x2b],
    note: "the firmware never reads these bytes of an entry, nor the cache byte (+2) and the two spare bytes (+6, +7) of any slot: a flip of all 30 at once changes no engine value, no display and no DSP word. +0x19, the byte stage 1 calls the target, is one of them", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.slots", kind: "modTable", offset: 0x2c, stride: 8, count: 6,
    note: "six slots of eight bytes, each one modulation: source (0 envelope, 1 LFO, anything else off), target, cache, strength from, strength to, follows MOD. DEPTH, two spare. The 72 types fill slot 0 (and slot 1 on four pitch types); slots 1 and 5 were filled by hand and work. The sixth slot's last four bytes are the first four bytes of the next window", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.slotTargets", kind: "modTable", note: "slot target 1 pitch, 2 OSC, 3 filter, 8 level, 9 pan, 10 IFX add to the destination of that number; 4 to 7 do too (no type uses them), 0 and 11 or more add nothing. Peak at strength 50: pitch 3481, filter 20000 (quadratic in the strength), every other 12800", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.strength", kind: "modTable", note: "strength at MOD. DEPTH d (0 to 127) is lo + (((hi - lo + 1) * (2d + 1)) >> 8) for 0 <= lo < hi; hi <= 0 mirrors it (lo and hi swap sign, the result is negative); lo < 0 with hi > 0 means 0 to 63; above 63 clamps to 63. A follow byte of 0 uses the type's default depth (+0x1A) instead of d. Equal to the RAM in 648 combinations of type, part and depth and speed", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.curve", kind: "modTable", offset: 0x1c, note: "waveform of the LFO unit: 0 falling saw, 1 square, 2 triangle, 3 sample and hold, 4 random, 5 unipolar square, 6 sine, 7 as 4; 8 to 16 give the saw of 0 and 255 the sample and hold: the index runs past an eight byte table. Envelope types run their LFO unit at rate 0, so the curve only sets a constant there", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.lfoSpeed", kind: "modTable", offset: 0x1e, note: "+0x1E clear: MOD. SPEED gives a rate index from the pair +0x20 to +0x21 (0 stands still, 16 gives 5.9 s, 64 gives 0.21 s, 127 gives 10 ms per cycle); set: a note step 1 to 16 (step 8 is one beat at any tempo, step 1 sixteen beats, 16 a 64th); above 16 runs as 16. A pair with lo above hi turns the knob around", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.egSpeed", kind: "modTable", offset: 0x28, note: "the pair +0x28 to +0x29 gives the envelope time from MOD. SPEED; +0x24 set reads it as a note step of the tempo (1 to 16, larger acts as 16), clear as a rate index (decay to half: 27 ms at 20, 137 ms at 50, 638 ms at 100)", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.phaseReset", kind: "modTable", offset: 0x1d, note: "set: the LFO phase goes back to 0 at some note starts (5 to 7 of 7 in a row of notes, depending on the moment; the condition is open); clear: at none", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.engine", kind: "modTable", note: "the engine that adds the six slots runs only while the part sounds; per part the firmware keeps nine bytes (speed outputs 0 to 2, strengths 0 to 5) and recomputes them when the type, MOD. DEPTH or MOD. SPEED changes", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.scratchRecord", kind: "modTable", note: "a record named for Voicing sits outside the table; once a flag byte is nonzero every type lookup returns it. The code that sets the flag and fills the record belongs to one host command handler (read, not run); in every run the flag stayed 0", source: "measured", evidence: MOD_STAGE2 },
  { id: "modType.copy", kind: "modTable", note: "an edit of the table at the RAM copy the firmware reads gives the same engine values as the same edit in a booted file copy; the same edit in Korg's copy at file 0xD82EC changes nothing", source: "measured", evidence: MOD_STAGE2 },
];
