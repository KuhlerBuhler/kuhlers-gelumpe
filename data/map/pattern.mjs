/**
 * The pattern block, 0x4000 bytes. The same block travels in a pattern
 * backup (.e2sallpat), a single pattern file (.e2spat), the pattern SysEx
 * dump and the flash; where it sits in each is the address module's job.
 *
 * Offsets are relative to the start of the block.
 */
const PATTERN_DIFF = "measure:2026-09-16/pattern-diff";
const CC = "measure:2026-09-16/cc-map";
const CHAIN = "measure:2026-10-10/pattern-kette-import";
const SPEC = "korg-spec:MIDI Implementation, Table 1";
const PART_SPEC = "korg-spec:MIDI Implementation, Table 6";
const MOTION_SPEC = "korg-spec:MIDI Implementation, Table 5";

const TRANSPORT = ["pattern-sysex", "e2sallpat", "e2spat"];
const PART = [{ count: 16, stride: 0x330, label: { de: "Part", en: "Part" } }];
const STEP = [...PART, { count: 64, stride: 12, label: { de: "Step", en: "Step" } }];
const PART_BASE = 0x800;
const STEP_BASE = PART_BASE + 0x30;

const l = (de, en = de) => ({ de, en });

const f = (id, label, offset, rest) => ({
  id, label, where: { offset }, type: "u8", transport: TRANSPORT, ...rest,
});

const part = (id, label, k, rest) =>
  f(`part.${id}`, label, PART_BASE + k, { area: "parts", repeat: PART, ...rest });

const step = (id, label, k, rest) =>
  f(`step.${id}`, label, STEP_BASE + k, { area: "steps", repeat: STEP, ...rest });

export default {
  block: "pattern",
  size: 0x4000,
  label: l("Pattern"),
  fields: [
    f("pattern.magic", l("Kennung"), 0, { area: "pattern", type: "bytes:4", edit: "readonly", source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.size", l("Größe", "Size"), 4, { area: "pattern", type: "u32le", edit: "readonly", source: "korg-spec", evidence: SPEC }),
    f("pattern.version", l("Pattern-Version", "Pattern version"), 12, { area: "pattern", type: "bytes:4", edit: "readonly", source: "korg-spec", evidence: SPEC }),
    f("pattern.name", l("Name"), 16, { area: "pattern", type: "latin1:16", source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.tempo", l("Tempo"), 34, { area: "pattern", type: "u16le", convert: "tempoBpm", unit: "BPM", range: [200, 3000], source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.swing", l("Swing"), 36, { area: "pattern", type: "s8", convert: "signed63", range: [-48, 48], source: "korg-spec", evidence: SPEC }),
    f("pattern.length", l("Länge", "Length"), 37, { area: "pattern", convert: "patternLength", range: [0, 3], source: "korg-spec", evidence: SPEC }),
    f("pattern.beat", l("Beat"), 38, { area: "pattern", convert: "beat", range: [0, 4], source: "measured", evidence: "measure:2026-10-29/beat-achtel", note: "4 (8tel) nur mit BLECH; Korgs Firmware kennt 0 bis 3 und spielt 4 mit einem Step alle 2 ms" }),
    f("pattern.key", l("Tonart", "Key"), 39, { area: "pattern", convert: "key", range: [0, 11], source: "korg-spec", evidence: SPEC }),
    f("pattern.scale", l("Tonleiter", "Scale"), 40, { area: "pattern", convert: "scale", range: [0, 34], source: "korg-spec", evidence: SPEC }),
    f("pattern.chordset", l("Chord Set"), 41, { area: "pattern", convert: "plain", range: [0, 4], source: "korg-spec", evidence: SPEC }),
    f("pattern.playLevel", l("Lautstärke", "Play level"), 42, { area: "pattern", convert: "playLevel", range: [0, 127], source: "korg-spec", evidence: SPEC }),
    f("pattern.mfx.type", l("Master-Effekt", "Master effect"), 61, { area: "master", convert: "plain", range: [0, 99], source: "measured", evidence: PATTERN_DIFF, note: "Platz im Master-Menü, mit Hacktribe über Korgs Bereich hinaus" }),
    f("pattern.mfx.padX", l("Pad X, zuletzt", "Pad X, last"), 62, { area: "master", convert: "plain", range: [0, 127], source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.mfx.padY", l("Pad Y, zuletzt", "Pad Y, last"), 63, { area: "master", convert: "plain", range: [0, 127], source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.mfx.hold", l("Pad halten", "Pad hold"), 65, { area: "master", convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    f("pattern.alternate1314", l("Alternate 13-14"), 68, { area: "pattern", convert: "onOff", range: [0, 1], source: "korg-spec", evidence: SPEC }),
    f("pattern.alternate1516", l("Alternate 15-16"), 69, { area: "pattern", convert: "onOff", range: [0, 1], source: "korg-spec", evidence: SPEC }),
    f("pattern.touchScale", l("Touch Scale, unbekannt", "Touch scale, unknown"), 44, { area: "pattern", type: "bytes:16", edit: "expert", source: "unknown",
      note: "Korgs Tabelle legt Touch Scale und Master FX hierhin; Master FX liegt gemessen 8 Byte weiter. Bis das geklärt ist, ist der Bereich unbekannt." }),

    f("pattern.chainTo", l("Chain To"), 15104, { area: "pattern", convert: "plain255", range: [0, 250], source: "measured", evidence: CHAIN,
      note: "Nummer des Ziel-Patterns, von 1 gezählt; 0 heißt keine Kette. Byte 15105 ist in allen 250 Patterns 0" }),
    f("pattern.chainRepeat", l("Chain Repeat"), 15106, { area: "pattern", convert: "plain", range: [0, 127], source: "measured", evidence: CHAIN,
      note: "Das Gerät zeigt 0 und 1 beide als 1; ein auf 3 gestellter Wert steht im Byte als 3" }),

    f("motion.part", l("Motion: Part"), 256, { area: "motion", repeat: [{ count: 24, stride: 1, label: l("Slot") }], convert: "motionPart", range: [0, 17], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC, note: "am Gerät nicht geprüft" }),
    f("motion.destination", l("Motion: Ziel", "Motion: destination"), 280, { area: "motion", repeat: [{ count: 24, stride: 1, label: l("Slot") }], convert: "motionDestination", range: [0, 19], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC, note: "am Gerät nicht geprüft" }),
    f("motion.value", l("Motion: Wert", "Motion: value"), 304, { area: "motion", repeat: [{ count: 24, stride: 64, label: l("Slot") }, { count: 64, stride: 1, label: l("Schritt", "Step") }], convert: "plain", range: [0, 127], edit: "expert", source: "korg-spec", evidence: MOTION_SPEC,
      note: "am Gerät nicht geprüft. Korgs Text nennt 49 als Beginn, die Tabellengröße 1584 = 24 + 24 + 24 * 64 geht nur ab 48 auf." }),

    part("lastStep", l("Last Step, unbekannt", "Last step, unknown"), 0, { edit: "expert", source: "unknown", note: "in allen Werks-Parts 0, Bedeutung offen" }),
    part("mute", l("Stumm", "Mute"), 1, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    part("voiceAssign", l("Voice Assign"), 2, { convert: "voiceAssign", range: [0, 3], source: "korg-spec", evidence: PART_SPEC }),
    part("motionMode", l("Motion Sequence"), 3, { convert: "motionMode", range: [0, 2], source: "korg-spec", evidence: PART_SPEC }),
    part("padVelocity", l("Pad-Velocity", "Pad velocity"), 4, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC }),
    part("scaleMode", l("Scale Mode"), 5, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC }),
    part("priority", l("Part-Priorität", "Part priority"), 6, { convert: "priority", range: [0, 1], source: "korg-spec", evidence: PART_SPEC }),
    part("sample", l("Sample"), 8, { type: "u16le", convert: "sampleSlot", range: [0, 999], source: "measured", evidence: PATTERN_DIFF, note: "Slot-Nummer des Samples" }),
    part("oscEdit", l("Osc Edit"), 11, { convert: "plain", range: [0, 127], source: "measured", evidence: CC }),
    part("filterType", l("Filtertyp", "Filter type"), 12, { convert: "filterType", range: [0, 16], source: "measured", evidence: "measure:2026-09-17/filter-types" }),
    part("cutoff", l("Cutoff"), 13, { convert: "cutoffHz", unit: "Hz", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/cutoff-resonance-peak" }),
    part("resonance", l("Resonanz", "Resonance"), 14, { convert: "resonanceDb", unit: "dB", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/cutoff-resonance-peak" }),
    part("egInt", l("Filter EG Int"), 15, { type: "s8", convert: "signed63", range: [-63, 63], source: "measured", evidence: PATTERN_DIFF }),
    part("modType", l("Modulation"), 16, { convert: "modType", range: [0, 71], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("modSpeed", l("Mod Speed"), 17, { convert: "modSpeed", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("modDepth", l("Mod Depth"), 18, { convert: "plain", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/mod-speed-depth" }),
    part("attack", l("Attack"), 20, { convert: "envTime", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/envelope-time" }),
    part("decay", l("Decay/Release"), 21, { convert: "envTime", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/envelope-time" }),
    part("level", l("Amp Level"), 24, { convert: "plain", range: [0, 127], source: "measured", evidence: CC }),
    part("pan", l("Panorama", "Pan"), 25, { type: "s8", convert: "pan", range: [-63, 63], source: "measured", evidence: PATTERN_DIFF }),
    part("egOn", l("Hüllkurve an", "EG on"), 26, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC }),
    part("mfxSend", l("MFX Send"), 27, { convert: "onOff", range: [0, 1], source: "korg-spec", evidence: PART_SPEC }),
    part("grooveType", l("Groove"), 28, { convert: "plain", range: [0, 24], source: "korg-spec", evidence: PART_SPEC }),
    part("grooveDepth", l("Groove-Tiefe", "Groove depth"), 29, { convert: "plain", range: [0, 127], source: "korg-spec", evidence: PART_SPEC }),
    part("ifxOn", l("IFX an", "IFX on"), 32, { convert: "onOff", range: [0, 1], source: "measured", evidence: CC }),
    part("ifxType", l("Insert-Effekt", "Insert effect"), 33, { convert: "plain", range: [0, 99], source: "measured", evidence: PATTERN_DIFF, note: "Platz im Insert-Menü, mit Hacktribe über Korgs Bereich hinaus" }),
    part("ifxEdit", l("IFX Edit"), 34, { convert: "plain", range: [0, 127], source: "measured", evidence: CC }),
    part("pitch", l("Osc Pitch"), 36, { type: "s8", convert: "oscPitchCents", unit: "Cent", range: [-63, 63], source: "measured", evidence: "measure:2026-09-17/osc-pitch" }),
    part("glide", l("Glide"), 37, { convert: "glideMs", unit: "ms", range: [0, 127], source: "measured", evidence: "measure:2026-09-17/glide-time",
      transport: ["e2sallpat", "e2spat", "cc"], note: "Pattern senden verwirft dieses Byte; am Gerät geht es nur per CC 81" }),
    part("byte38", l("Byte 38, unbekannt", "Byte 38, unknown"), 38, { edit: "expert", source: "unknown", note: "belegt, Bedeutung unbekannt" }),

    step("on", l("An", "On"), 0, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    step("gate", l("Gate"), 1, { convert: "gateTime", range: [0, 127], source: "korg-spec", evidence: PART_SPEC, note: "255 kommt oft vor und ist ungeklärt" }),
    step("velocity", l("Velocity"), 2, { convert: "plain", range: [1, 127], source: "measured", evidence: PATTERN_DIFF }),
    step("trigger", l("Trigger"), 3, { convert: "onOff", range: [0, 1], source: "measured", evidence: PATTERN_DIFF }),
    f("step.note", l("Note"), STEP_BASE + 4, { area: "steps", repeat: [...STEP, { count: 4, stride: 1, label: l("Note") }], convert: "stepNote", range: [0, 128], source: "measured", evidence: PATTERN_DIFF }),
  ],
};
